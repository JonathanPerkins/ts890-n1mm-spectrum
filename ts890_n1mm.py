#!/usr/bin/env python3

'''
Script to connect to a Kenwood TS-890S, read the spectrum data and
forward to an instance of N1MM+ logger.
'''

import asyncio
from asyncio import Queue
import argparse

# TS-890 KNS TCP/IP control port
KNS_CTRL_PORT = 60000

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
    ''' TS-890 connection configuration '''
    def __init__(self, host, user, password):
        self._host = host
        self._user = user
        self._password = password

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

#--------------------------------------------------------------
# Spectrum data class
#--------------------------------------------------------------

class SpectrumData:
    ''' One line of spectrum data '''
    def __init__(self, data):
        self._data = data

    @property
    def data(self):
        ''' Returns the data '''
        return self._data

    @data.setter
    def data(self, data):
        ''' Sets the ID '''
        self._data = data

#--------------------------------------------------------------
# Interface to N1MM+
#--------------------------------------------------------------

async def send_to_n1mm(queue: Queue, n1mm_host):
    ''' Coroutine to read spectrum data from the queue
        and send to N1MM.
    '''
    while not queue.empty():
        sd: SpectrumData = await queue.get()
        print(sd.data)
        queue.task_done()

#--------------------------------------------------------------
# Interface to TS-890
#--------------------------------------------------------------

def handle_cat_bs(resp):
    ''' Handle a BSx cat response '''
    print(f'BSx rx: {resp}')

def handle_info(cat_msg):
    ''' Handle received messages from the TS-890 '''
    # CAT response handlers
    resp_handlers = {
        'BS': handle_cat_bs
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
            resp_handlers[cmd](cat_msg)
    else:
        # Handle error responses
        print(f'ERROR: {cat_msg}')

async def handle_ai_cat(reader):
    ''' Coroutine to wait for AI CAT messages and handle them '''
    while True:
        try:
            resp = await reader.readuntil(separator=b';')
            handle_info(resp.decode())
        except asyncio.IncompleteReadError as err:
            pass

async def send_cmd(writer, cmd):
    ''' Wrapper for write and drain '''
    writer.write(cmd.encode())
    await writer.drain()

async def send_cmd_wait_response(reader, writer, cmd):
    ''' Wrapper for write and wait for response '''
    writer.write(cmd.encode())
    await writer.drain()
    resp = await reader.readuntil(separator=b';')
    if resp:
        resp = resp.decode()
    return resp

async def do_heartbeat(writer):
    ''' Coroutine to send regular heartbeat CAT cmds to TS-890 '''
    while True:
        # Might as well poll something useful - get bandscope mode
        await send_cmd(writer, 'BS3;')
        # Wait 5 seconds
        await asyncio.sleep(5)

async def fetch_from_ts890(queue: Queue, ts890: Ts890):
    ''' Coroutine to connect to TS-890, read spectrum data
        and save it in the queue
    '''
    print(f"Connecting to TS-890 {ts890.host}")
    reader, writer = await asyncio.open_connection(ts890.host, KNS_CTRL_PORT)

    # Start connection to TS-890 by sending ##CN;
    print('Sending CN')
    resp = await send_cmd_wait_response(reader, writer, '##CN;')
    # Response ##CNx; (x=1 ok, x=0 connection refused)
    if resp == '##CN1;':
        # Send ##ID & read response ##IDx; (x=1 ok, x=0 connection refused)
        print('Sending ID')
        resp = await send_cmd_wait_response(reader, writer, cat_id(ts890.user, ts890.password))
        if resp == '##ID1;':
            # Turn on auto information AI2;
            print('Sending AI')
            await send_cmd(writer, 'AI2;')
            # Poll for required info
            await send_cmd(writer, 'BS3;')
            await send_cmd(writer, 'BS4;')
            await send_cmd(writer, 'BSM;')
            # Run the AI response handler and heartbeat coroutines
            await asyncio.gather(
                    handle_ai_cat(reader),
                    do_heartbeat(writer)
            )


    # BS3; reads bandscope mode (centre/fixed/auto)

    #  FA; or FB; read receiver freq (for centre mode)
    #  BS4; reads bandscope span (for centre mode)
    # or:
    #  BSM; reads bandscope upper/lower freqs for fixed mode and auto scroll



    # Enable bandscope LAN output DD0

    # Receive one line of data (640 points) ##DD2

#--------------------------------------------------------------
# Main
#--------------------------------------------------------------

async def main(ts890, n1mm):
    ''' Main entry point: run client '''
    spectrum_queue = Queue()

    task1 = asyncio.create_task(
        fetch_from_ts890(spectrum_queue, ts890))

    task2 = asyncio.create_task(
        send_to_n1mm(spectrum_queue, n1mm))

    await task1
    await task2

if __name__ == '__main__':
    PARSER = argparse.ArgumentParser()

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
        ts890 = Ts890(ARGS.ts890, ARGS.user, ARGS.password)
        asyncio.run(main(ts890, ARGS.n1mm))
    except KeyboardInterrupt:
        print('Caught keyboard interrupt')
