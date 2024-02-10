# ts890-n1mm-spectrum

![overview](images/overview_image.png)

This is a Python script to read band scope data from a network connected Kenwood TS-890S and send it formatted as spectrum data to N1MM+ logger. It allows the user to see the TS-890's bandscope in a N1MM spectrum display window with spots overlaid:

![example N1MM spectrum display](images/example_n1mm_bandscope_1.png)

## Requirements

This is a self contained Python 3 script that should run without the need to install any extra Python modules. It has been tested on MacOS Sonoma with the default Python version 3.8.2, but should run on Linux or Windows if a suitable Python 3 is installed.

Installation is simply download the __ts890_n1mm.py__ file to a directory of your choice.

## Comand line options

### Minimal usage example:

```
./ts890_n1mm.py -t 192.168.1.89 -a AdminUserName -p AdminPassword -n 192.168.1.11
```

In the above example, the TS-890 has an IP address of _192.168.1.89_ and has an admin user called _AdminUserName_ with a password of _AdminPassword_. The Windows PC running N1MM+ has an IP address of _192.168.1.11_. For more clarity the alternative long form of option names can be used:

```
./ts890_n1mm.py --ts890 192.168.1.89 --admin AdminUserName --password AdminPassword --n1mm 192.168.1.11
```

### Displaying help

Use the _--help_ command line option to list all options:

```
./ts890_n1mm.py --help
usage: ts890_n1mm.py [-h] -t <host or addr> -p <password> (-a <admin account> | -u <user account>) [-n <host or addr>]

Script to read bandscope data from a TS-890S and send it to N1MM+ logger.

optional arguments:
  -h, --help            show this help message and exit

TS-890 options:
  -t <host or addr>, --ts890 <host or addr>
                        TS-890 IP address or hostname
  -p <password>, --password <password>
                        TS-890 account password

Specify either an admin or user account for the TS-890:
  -a <admin account>, --admin <admin account>
                        TS-890 admin account name
  -u <user account>, --user <user account>
                        TS-890 user account name

N1MM options:
  -n <host or addr>, --n1mm <host or addr>
                        N1MM IP address or hostname
```

### Loading arguments from a file

Command line arguments can be placed in a text file and loaded using the '@' argument, e.g:

```
./ts890_n1mm.py @my_config.cfg
```

Where _my_cfg.cfg_ for the previous example would contain:

```
--ts890=192.168.1.89
--admin=AdminUserName
--password=AdminPassword
--n1mm=192.168.1.11
```

Note: each argument must be on a new line and use the _--option=value_ format with an equals sign and no whitespace.

# License

This software is offered with no warranty or liability and is licensed under the permissive open source MIT license.

Copyright (c) 2024 Jonathan Perkins G4IVV.
