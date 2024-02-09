# ts890-n1mm-spectrum

This is a Python script to send spectrum data from a network connected Kenwood TS-890S to N1MM+ logger.

![overview](images/overview_image.png)

It allows the user to see the TS-890's bandscope in a N1MM spectrum display window with spots overlaid:

![example N1MM spectrum display](images/example_n1mm_bandscope_1.png)

## Requirements

This is a self contained Python 3 script that should run without the need to install any extra Python modules. It has been tested on MacOS Sonoma with the default Python version 3.8.2, but should run on Linux or Windows if a suitable Python 3 is installed.

Installation is simply download the __ts890_n1mm.py__ file to a directory of your choice.

## Comand line options

### Minimal usage example:

```bash
./ts890_n1mm.py -t 192.168.1.89 -u TS890_AdminUserName -p TS890_AdminPassword -n 192.168.1.11
```

In the above example, the TS-890 has an IP address of __192.168.1.89__ and has a KVS admin user called __TS890_AdminUserName__ with a password of __TS890_AdminPassword__. The Windows PC running N1MM+ has an IP address of __192.168.1.11__.

### Displaying help

Use the __--help__ command line option to list all options:

```bash
./ts890_n1mm.py --help
usage: ts890_n1mm.py [-h] -t <host or addr> -u <username> -p <password> [-n <host or addr>]

optional arguments:
  -h, --help            show this help message and exit
  -t <host or addr>, --ts890 <host or addr>
                        TS-890 IP address or hostname
  -u <username>, --username <username>
                        TS-890 username
  -p <password>, --password <password>
                        TS-890 password
  -n <host or addr>, --n1mm <host or addr>
                        N1MM IP address or hostname
```

### Loading arguments from a file

Command line arguments can be placed in a text file and loaded by:

```bash
$ ./ts890_n1mm.py @my_config.cfg
```

Where __my_cfg.cfg__ for the previous example would be:

```
--ts890=192.168.1.89
--username=TS890_AdminUserName
--password=TS890_AdminPassword
--n1mm=192.168.1.11
```

Note: each argument must be on a new line and use the __--option=value__ format with an equals sign and no whitespace.