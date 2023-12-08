# CPU staker

Force the current workload of the OS to be consolidated on the smallest count of CPUs possible (instead of being spread).
> We fully use CPU0 before using CPU1, CPU1 before CPU2, and so on

## Features

Use core disabling facilities of linux  
Intended to be use in a VM! No SMT consideration here

## Usage

```bash
sudo python3 cpu-staker.py --help
```

Current state (cpu0 cannot be disabled)
```bash
grep '' /sys/devices/system/cpu/cpu*/online
```

## Set up as daemon

Once cpustaker.service was adapted according to your needs:
```bash
sudo cp cpustaker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable cpustaker
sudo systemctl start cpustaker
sudo systemctl status cpustaker
```

