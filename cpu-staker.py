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

    def read_state(self):
        if self.cpu_id == 0: return '1'
        with open(self.path, 'r') as f:
            content = f.read()
        return content

    def read_state_as_int(self):
        return int(self.read_state())

    def read_state_as_bool(self):
        return bool(self.read_state())

    def update_state(self, active : bool = True):
        if self.cpu_id == 0: return # core0 cannot be disabled

        def change_core_state(path, content = str):
            with open(path, 'w') as f:
                f.write(content)
                
        content = '0'
        if active: content = '1'
        if int(content) != self.read_state_as_int(): 
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

def get_usage_global(cpu_time_hist : dict):
    with open(SYSFS_STAT, 'r') as f:
        split = f.readlines()[0].split(' ')
        split.remove('')
    if 'global' not in cpu_time_hist: cpu_time_hist['global'] = CpuTime()
    return __get_usage_of_line(split=split, hist_object=cpu_time_hist['global'])

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

def update_active_cores(last_usage : float, usage_list : list, cpu_changers : dict):

    active_cores_count = 0
    for cpu_changer in cpu_changers.values(): active_cores_count += cpu_changer.read_state_as_int()
    margin = 0.2
    considered_usage = math.ceil(last_usage*active_cores_count + margin)

    for cpu_id, cpu_changer in cpu_changers.items():

        if cpu_id < considered_usage: # cpu_id start at 0 so <
            cpu_changer.update_state(active=True)
        else:
            cpu_changer.update_state(active=False)
    
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

    cpu_time_hist = dict()
    usage_list    = list()
    try:
        while True:
            usage = get_usage_global(cpu_time_hist=cpu_time_hist)
            if usage != None: update_active_cores(last_usage=usage, usage_list=usage_list, cpu_changers=cpu_changers)
            time.sleep(0.2)

    except KeyboardInterrupt:
        print('Program interrupted: Re-enabling all CPU')
        for cpu_changer in cpu_changers.values(): cpu_changer.update_state(active=True)
        for cpu_changer in cpu_changers.values(): cpu_changer.wait_for_completion()
        sys.exit(0)