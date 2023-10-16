import os, sys, getopt, threading, re, time, math
from os import listdir
from os.path import isfile, join, exists

SYSFS_TOPO    = '/sys/devices/system/cpu/'
SYSFS_STAT    = '/proc/stat'
# From https://www.kernel.org/doc/Documentation/filesystems/proc.txt
SYSFS_STATS_KEYS  = {'cpuid':0, 'user':1, 'nice':2 , 'system':3, 'idle':4, 'iowait':5, 'irq':6, 'softirq':7, 'steal':8, 'guest':9, 'guest_nice':10}
SYSFS_STATS_IDLE  = ['idle', 'iowait']
SYSFS_STATS_NTID  = ['user', 'nice', 'system', 'irq', 'softirq', 'steal']

def print_usage():
    print('sudo python3 cpu-staker.py')

class StateChanger(object):

    def __init__(self, cpu_id : int):
        self.cpu_id = cpu_id
        self.path   = SYSFS_TOPO + 'cpu' + str(cpu_id) + '/online'
        self.thread = None

    def set_state(self, active : bool = True):
        if self.cpu_id == 0: return # Impossible to disable cpu0

        def change_core_state(path, content = str):
            with open(path, 'w') as f:
                f.write(content)
                
        content = '1'
        if (not active): content = '0'
        changed_needed = False
        with open(self.path, 'r') as f:
                if(f.read() == content): changed_needed = True

        if changed_needed:
            self.thread = threading.Thread(target=change_core_state, args=(self.path, content))
            self.thread.start()

    def wait_for_completion(self):
        if self.thread != None: self.thread.join()

class CpuTime(object):
    def has_time(self):
        return hasattr(self, 'idle') and hasattr(self, 'not_idle')

    def set_time(self, idle : int, not_idle : int):
        setattr(self, 'idle', idle)
        setattr(self, 'not_idle', not_idle)

    def get_time(self):
        return getattr(self, 'idle'), getattr(self, 'not_idle')

    def clear_time(self):
        if hasattr(self, 'idle'): delattr(self, 'idle')
        if hasattr(self, 'not_idle'): delattr(self, 'not_idle')

def get_cpu_list():
    regex = '^cpu[0-9]+$'
    cpu_found = [int(re.sub("[^0-9]", '', f)) for f in listdir(SYSFS_TOPO) if not isfile(join('topology', f)) and re.match(regex, f)]
    return set(cpu_found)

def get_usage_global(cputime_hist : dict):
    with open(SYSFS_STAT, 'r') as f:
        split = f.readlines()[0].split(' ')
        split.remove('')
    if 'global' not in cputime_hist: cputime_hist['global'] = CpuTime()
    return __get_usage_of_line(split=split, hist_object=cputime_hist['global'])

def __get_usage_of_line(split : list, hist_object : object, update_history : bool = True):
    idle          = sum([ int(split[SYSFS_STATS_KEYS[idle_key]])     for idle_key     in SYSFS_STATS_IDLE])
    not_idle      = sum([ int(split[SYSFS_STATS_KEYS[not_idle_key]]) for not_idle_key in SYSFS_STATS_NTID])

    # Compute delta
    cpu_usage  = None
    if hist_object.has_time():
        prev_idle, prev_not_idle = hist_object.get_time()
        delta_idle     = idle - prev_idle
        delta_total    = (idle + not_idle) - (prev_idle + prev_not_idle)
        if delta_total>0: # Manage overflow
            cpu_usage = ((delta_total-delta_idle)/delta_total)
    
    if update_history: hist_object.set_time(idle=idle, not_idle=not_idle)
    return cpu_usage

def disable_unused(usage : float, cpu_changers : dict):
    considered_usage = max([math.ceil(usage) + 2, 1])
    for cpu_id, cpu_changer in cpu_changers.items():
        if cpu_id <= considered_usage:
            #print(cpu_id, 'considered used')
            cpu_changer.set_state(active=True)
        else:
            #print(cpu_id, 'considered unused')
            cpu_changer.set_state(active=False)
    
    for cpu_changer in cpu_changers.values(): cpu_changer.wait_for_completion()

if __name__ == '__main__':
    short_options = 'h'
    long_options = ['help']

    try:
        arguments, values = getopt.getopt(sys.argv[1:], short_options, long_options)
    except getopt.error as err:
        print(str(err))
        print_usage()
    for current_argument, current_value in arguments:
        if current_argument in ('-h', '--help'):
            print_usage()
            sys.exit(0)

    if os.geteuid() != 0:
        print('This program needs to be root')
        print_usage()
        sys.exit(0)

    cpu_list = get_cpu_list()
    cpu_list_len = len(cpu_list)
    cpu_changers = {cpu : StateChanger(cpu_id=cpu) for cpu in cpu_list}
    print('Found', cpu_list_len, 'cores :', cpu_list)
    delta_dict = dict()

    try:
        while True:
            global_usage = get_usage_global(cputime_hist=delta_dict)
            if global_usage != None:
                global_usage*=cpu_list_len
                disable_unused(usage=global_usage, cpu_changers=cpu_changers)
            time.sleep(5)

    except KeyboardInterrupt:
        print('Program interrupted: Re-enabling all CPU')
        for cpu_changer in cpu_changers.values(): cpu_changer.set_state(active=True)
        for cpu_changer in cpu_changers.values(): cpu_changer.wait_for_completion()
        sys.exit(0)