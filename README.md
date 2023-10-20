# CPU staker

Force workload consolidation of CPU (fully use core0 before using core1, and so on)

## Features

Use disabling facilities of linux  
Intended to be use in a VM! No SMT consideration here

## Usage

```bash
sudo python3 cpu-staker.py --help
```

Current state (cpu0 cannot be disabled)
```bash
grep '' /sys/devices/system/cpu/cpu*/online
```
