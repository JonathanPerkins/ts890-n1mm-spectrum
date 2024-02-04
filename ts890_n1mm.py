#!/usr/bin/env python3

'''
Script to connect to a Kenwood TS-890S, read the spectrum data and
forward to an instance of N1MM+ logger.
'''

import asyncio
from asyncio import Queue
import argparse
import xml.etree.ElementTree as ET


# TS-890 KNS TCP/IP control port
KNS_CTRL_PORT = 60000

# N1MM+ UDP port for spectrum data
N1MM_SPECTRUM_PORT = 13064

#--------------------------------------------------------------
# Helper classes
#--------------------------------------------------------------

class AppException(Exception):
    ''' Exception for script errors '''
    def __init__(self, value, additional='', context=''):
        self._context = context
        self._additional = additional
        super(Exception, self).__init__(value)

    def add_context(self, context_str):
        ''' Add a further context string to the exception arguments '''
        if not self._context:
            self._context = context_str
        else:
            self._context = f"{context_str}: {self._context}"

    @property
    def context(self):
        ''' Getter for context '''
        return self._context

    @property
    def additional(self):
        ''' Getter for additional info '''
        return self._additional

#--------------------------------------------------------------
# TS-890 CAT command helpers
#--------------------------------------------------------------

def cat_id(username, password):
    ''' Format an adminstrator ID login command '''
    return f'##ID0{len(username):02}{len(password):02}{username}{password};'

#--------------------------------------------------------------
# TS-890 class
#--------------------------------------------------------------

class Ts890:
    ''' TS-890 configuration and status '''
    def __init__(self, host, user, password):
        self._host = host
        self._user = user
        self._password = password
        self._bs_mode = None
        self._bs_span_hz = None
        self._bs_lower_hz = None
        self._bs_upper_hz = None
        self._receiver_vfo = None

    @property
    def host(self):
        ''' Returns the hostname/IP address '''
        return self._host

    @property
    def user(self):
        ''' Returns the username to login to the TS-890 '''
        return self._user

    @property
    def password(self):
        ''' Returns the password to login to the TS-890 '''
        return self._password

    @property
    def bs_mode(self):
        ''' Returns the bandscope mode '''
        # 0=centre, 1=fixed, 2=auto scroll
        return self._bs_mode
    @bs_mode.setter
    def bs_mode(self, mode):
        ''' Sets the bandscope mode '''
        modes = ['centre', 'fixed', 'auto scroll']
        if  0 <= mode < len(modes) and mode != self._bs_mode:
            self._bs_mode = mode
            print(f'Bandscope {modes[mode]} mode')
            # Centre mode: invalidate freqs until VFO read
            if self.is_centre_mode:
                self._bs_lower_hz = None
                self._bs_upper_hz = None
    @property
    def is_centre_mode(self):
        ''' True if bandscope is in centre mode '''
        return self._bs_mode == 0

    @property
    def bs_lower_hz(self):
        ''' Returns the bandscope lower edge frequency in Hz '''
        return self._bs_lower_hz
    @bs_lower_hz.setter
    def bs_lower_hz(self, lower_hz):
        ''' Sets bandscope lower frequency in Hz (Integer) '''
        self._bs_lower_hz = lower_hz

    @property
    def bs_upper_hz(self):
        ''' Returns the bandscope upper edge frequency in Hz '''
        return self._bs_upper_hz
    @bs_upper_hz.setter
    def bs_upper_hz(self, upper_hz):
        ''' Sets bandscope upper frequency in Hz (Integer) '''
        self._bs_upper_hz = upper_hz

    @property
    def bs_span_hz(self):
        ''' Returns the bandscope span '''
        return self._bs_span_hz
    @bs_span_hz.setter
    def bs_span_hz(self, span):
        ''' Sets the bandscope span '''
        spans = [5000, 10000, 20000, 30000, 50000, 100000, 200000, 500000]
        if 0 <= span < len(spans) and span != self._bs_span_hz:
            self._bs_span_hz = spans[span]
            print(f'Bandscope span {self._bs_span_hz}Hz')

    @property
    def receiver_vfo(self):
        ''' Returns the receiver VFO source '''
        return self._receiver_vfo
    @receiver_vfo.setter
    def receiver_vfo(self, vfo):
        ''' Sets the receiver VFO source '''
        rx_vfo = ['VFO A', 'VFO B', 'Memory channel']
        if 0 <= vfo < len(rx_vfo) and vfo != self._receiver_vfo:
            self._receiver_vfo = vfo
            print(f'Receiver {rx_vfo[vfo]}')
    @property
    def vfo_a_active(self):
        ''' True if VFO A is active '''
        return self._receiver_vfo == 0
    @property
    def vfo_b_active(self):
        ''' True if VFO B is active '''
        return self._receiver_vfo == 1

    def has_all_required_info(self):
        ''' Returns True if all the required information
            to send spectrum information to N1MM is present,
            False otherwise.
        '''
        return self._bs_lower_hz and self._bs_upper_hz

#--------------------------------------------------------------
# Spectrum data class
#--------------------------------------------------------------

class SpectrumData:
    ''' One line of spectrum data '''
    def __init__(self, ts890: Ts890, data):
        self._data = data
        self._lower_hz = ts890.bs_lower_hz
        self._upper_hz = ts890.bs_upper_hz

    @property
    def data(self):
        ''' Returns the data '''
        return self._data
    @data.setter
    def data(self, data):
        ''' Sets the data '''
        self._data = data
    @property
    def num_data_points(self):
        ''' Returns the number of data points '''
        return len(self._data)

    @property
    def lower_hz(self):
        ''' Returns the low edge frequency in Hz '''
        return self._lower_hz
    @property
    def upper_hz(self):
        ''' Returns the high edge frequency in Hz '''
        return self._upper_hz

#--------------------------------------------------------------
# Interface to N1MM+
#--------------------------------------------------------------

class N1mmSpectrumProtocol:
    ''' Protocol implementation for UDP connection to N1MM '''
    def __init__(self):
        self.transport = None

    def connection_made(self, transport):
        ''' UDP transport has been created '''
        self.transport = transport

    def connection_lost(self, exc):
        ''' Mandatory connection_lost method '''
        # The socket has been closed
        print(f'N1MM transport closed: {exc}')

    def datagram_received(self, data, addr):
        ''' UDP datagram received callback '''
        message = data.decode()
        # Not expecting anything back from N1MM, but
        # log it if we do
        print(f'Received {message} from {addr}')

async def send_to_n1mm(queue: Queue, n1mm_host):
    ''' Coroutine to read spectrum data from the queue
        and send to N1MM.
    '''
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: N1mmSpectrumProtocol(),
        remote_addr=(n1mm_host, N1MM_SPECTRUM_PORT))
    try:
        while True:
            sdata: SpectrumData = await queue.get()
            # Build the XML structure
            try:
                spectrum = ET.Element('Spectrum')
                ET.SubElement(spectrum, 'Name').text='TS-890'
                # Frequencies rounded to nearest kHz
                ET.SubElement(spectrum, 'LowScopeFrequency').text=str(sdata.lower_hz/1000)
                ET.SubElement(spectrum, 'HighScopeFrequency').text=str(sdata.upper_hz/1000)
                ET.SubElement(spectrum, 'ScalingFactor').text='0.5'
                ET.SubElement(spectrum, 'DataCount').text=str(sdata.num_data_points)
                ET.SubElement(spectrum, 'SpectrumData').text=','.join(map(str, sdata.data))
                xml_str = ET.tostring(spectrum, encoding='utf8', xml_declaration=True)
                # print(f'{xml_str[:300].decode()}')
                await transport.sendto(xml_str)
            except TypeError:
                pass
            queue.task_done()
    finally:
        transport.close()

#--------------------------------------------------------------
# Interface to TS-890
#--------------------------------------------------------------

class Ts890Connection:
    ''' TS-890 connection implementation '''
    def __init__(self, queue: Queue, ts890: Ts890):
        self._queue = queue
        self._ts890 = ts890
        self._reader = None
        self._writer = None

    async def _handle_cat_bs(self, resp):
        ''' Handle a BSx cat response '''
        # All the BSx responses we are interested in have at least
        # one parameter, so minimum length with terminator is 5.
        if len(resp) > 4:
            cmd = resp[:3]
            if cmd == 'BSM':
                # BSM0.. contains the current bandscope edges, but not
                # for centre mode.
                if not self._ts890.is_centre_mode and len(resp) == 21 and resp[3] == '0':
                    # extract edge frequencies
                    try:
                        self._ts890.bs_lower_hz = int(resp[4:12])
                        self._ts890.bs_upper_hz = int(resp[12:20])
                    except ValueError:
                        print(f'error extracting frequencies from {resp}')
            elif cmd == 'BS3':
                try:
                    self._ts890.bs_mode = int(resp[3])
                    # Now in centre mode?
                    if self._ts890.is_centre_mode:
                        # Find out which VFO is active so new bandscope
                        # edge frequencies can be calculated
                        await self._send_cmd('FR;')
                except ValueError:
                    print(f'error extracting mode from {resp}')
            elif cmd == 'BS4':
                try:
                    self._ts890.bs_span_hz = int(resp[3])
                except ValueError:
                    print(f'error extracting span from {resp}')

    async def _handle_cat_dd(self, resp):
        ''' Handle a ##DDx cat response '''
        # Just interested in ##DD2 of fixed length
        if len(resp) == 1286 and resp[:5] == '##DD2':
            try:
                # Extract hex data, convert to integer and invert
                data = []
                for i in range(5,len(resp)-1,2):
                    val = int(resp[i:i+2],16)
                    # Convert value to N1MM scale
                    if val < 140:
                        val = 140 - val
                    else:
                        val = 0
                    data.append(val)
                sdata = SpectrumData(self._ts890, data)
                await self._queue.put(sdata)
            except ValueError:
                print('Failed to parse bandscope data')
        else:
            print(f'Ignoring unexpected ##DD: {resp}')

    async def _handle_cat_fr(self, resp):
        ''' Handle a FRx; cat response '''
        if len(resp) == 4:
            try:
                self._ts890.receiver_vfo = int(resp[2])
                # If centre mode is active, make sure we have the
                # current active VFO frequency.
                if self._ts890.is_centre_mode:
                    if self._ts890.vfo_a_active:
                        await self._send_cmd('FA;')
                    elif self._ts890.vfo_b_active:
                        await self._send_cmd('FB;')
            except ValueError:
                print(f'error extracting RX from {resp}')

    async def _handle_cat_fa_fb(self, resp):
        ''' Handle a FAx or FBx cat response '''
        # Only need VFO freq in bandscope centre mode
        if self._ts890.is_centre_mode and len(resp) == 14:
            # extract carrier frequency
            try:
                freq_hz = int(resp[2:13])
                # Calculate and store the bandscope lower and upper frequnencies
                self._ts890.bs_lower_hz = int(freq_hz - (self._ts890.bs_span_hz/2))
                self._ts890.bs_upper_hz = int(freq_hz + (self._ts890.bs_span_hz/2))
            except ValueError:
                print(f'error extracting frequency from {resp}')

    async def _handle_info(self, cat_msg):
        ''' Handle received messages from the TS-890 '''
        # CAT response handlers
        resp_handlers = {
            'BS': self._handle_cat_bs,
            'FR': self._handle_cat_fr,
            'FA': self._handle_cat_fa_fb,
            'FB': self._handle_cat_fa_fb,
            '##DD': self._handle_cat_dd
        }
        # Non-error messages are at least 3 characters in length
        # "XX...;" or "##XX...;" for LAN commands
        if len(cat_msg) > 2:
            # Extract CAT command
            cmd = cat_msg[:2]
            if cmd == '##':
                cmd = cat_msg[:4]
            # Call command handler, otherwise ignore
            if cmd in resp_handlers:
                await resp_handlers[cmd](cat_msg)
        else:
            # Handle error responses
            print(f'ERROR: {cat_msg}')

    async def _send_cmd(self, cmd):
        ''' Wrapper for write and drain '''
        self._writer.write(cmd.encode())
        await self._writer.drain()

    async def _send_cmd_wait_response(self, cmd):
        ''' Wrapper for write and wait for response '''
        self._writer.write(cmd.encode())
        await self._writer.drain()
        try:
            resp = await self._reader.readuntil(separator=b';')
            if resp:
                resp = resp.decode()
        except asyncio.IncompleteReadError as err:
            resp = None
            raise AppException(err, context='reading CAT response')
        return resp

    async def _do_cat_rx(self):
        ''' Coroutine to wait for CAT messages and handle them '''
        bandscope_on = False
        while True:
            try:
                resp = await self._reader.readuntil(separator=b';')
                await self._handle_info(resp.decode())
                # After each message is handled, determine if
                # bandscope data can be enabled/disabled
                if self._ts890.has_all_required_info():
                    if not bandscope_on:
                        # Enable bandscope data
                        await self._send_cmd('DD02;')
                        bandscope_on = True
                elif bandscope_on:
                    # Disable bandscope data
                    await self._send_cmd('DD00;')
                    bandscope_on = False
            except asyncio.IncompleteReadError as err:
                raise AppException(err, context='reading CAT from TS-890')

    async def _do_heartbeat(self):
        ''' Coroutine to send regular heartbeat CAT cmds to TS-890 '''
        while True:
            # Might as well poll something useful - get bandscope mode
            await self._send_cmd('BS3;')
            # Wait 5 seconds
            await asyncio.sleep(5)

    async def fetch_from_ts890(self):
        ''' Coroutine to connect to TS-890, read spectrum data
            and save it in the queue
        '''
        try:
            print(f"Connecting to TS-890 {self._ts890.host}")
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._ts890.host, KNS_CTRL_PORT),
                10)

            try:
                # Start connection to TS-890 by sending ##CN;
                resp = await self._send_cmd_wait_response('##CN;')
                # Response ##CNx; (x=1 ok, x=0 connection refused)
                if resp == '##CN1;':
                    # Send ##ID & read response ##IDx; (x=1 ok, x=0 connection refused)
                    resp = await self._send_cmd_wait_response(cat_id(self._ts890.user, self._ts890.password))
                    if resp == '##ID1;':
                        print('Connected OK')
                        # Turn on auto information AI2;
                        await self._send_cmd('AI2;')
                        # Poll for required info
                        await self._send_cmd('BS3;')
                        await self._send_cmd('BS4;')
                        await self._send_cmd('BSM0;')
                        await self._send_cmd('FR;')
                        # Run the CAT response handler and heartbeat coroutines
                        await asyncio.gather(
                                self._do_cat_rx(),
                                self._do_heartbeat()
                        )
                    else:
                        print('TS-890 login failure')
                else:
                    print('TS-890 connection refused')
            finally:
                self._writer.close()
                await self._writer.wait_closed()
        except asyncio.TimeoutError:
            raise AppException('timeout connecting to',
                               context='TS-890 connection',
                               additional=self._ts890.host)
        except OSError as exp:
            raise AppException(exp, 'connecting to TS-890')

#--------------------------------------------------------------
# Main
#--------------------------------------------------------------

async def main(ts890, n1mm):
    ''' Main entry point: run client '''
    spectrum_queue = Queue()

    try:
        ts890_connection = Ts890Connection(spectrum_queue, ts890)
        task1 = asyncio.create_task(
            ts890_connection.fetch_from_ts890())

        task2 = asyncio.create_task(
            send_to_n1mm(spectrum_queue, n1mm))

        await task1
        await task2
    except asyncio.TimeoutError:
        pass

if __name__ == '__main__':
    PARSER = argparse.ArgumentParser(fromfile_prefix_chars='@')

    PARSER.add_argument('-t', '--ts890',
                        required=True,
                        dest = 'ts890',
                        metavar = '<host or addr>',
                        help = 'TS-890 IP address or hostname')

    PARSER.add_argument('-u', '--username',
                        required=True,
                        dest = 'user',
                        metavar = '<username>',
                        help = 'TS-890 username')

    PARSER.add_argument('-p', '--password',
                        required=True,
                        dest = 'password',
                        metavar = '<password>',
                        help = 'TS-890 password')

    PARSER.add_argument('-n', '--n1mm',
                        dest = 'n1mm',
                        metavar = '<host or addr>',
                        help = 'N1MM IP address or hostname',
                        default = '127.0.0.1')

    ARGS = PARSER.parse_args()

    try:
        ts890_ctx = Ts890(ARGS.ts890, ARGS.user, ARGS.password)
        asyncio.run(main(ts890_ctx, ARGS.n1mm))
    except KeyboardInterrupt:
        print('Caught keyboard interrupt')
    except AppException as ex:
        print(f"Error: {ex.context}: {ex} {ex.additional}")
