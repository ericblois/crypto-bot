
MAGENTA = '\033[95m'
BLUE = '\033[94m'
CYAN = '\033[96m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
ENDC = '\033[0m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'


def str_red(string):
    return RED + str(string) + ENDC


def str_blu(string):
    return BLUE + str(string) + ENDC


def str_ylw(string):
    return YELLOW + str(string) + ENDC


def str_grn(string):
    return GREEN + str(string) + ENDC


def str_cyn(string):
    return CYAN + str(string) + ENDC


def str_mag(string):
    return MAGENTA + str(string) + ENDC

quantity_str = '{:0.0{}f}'.format(0.344554453, 5)
print(quantity_str)