
# Mirror Backups
#
# This script will create weekly snapshots of the ssd backup. Old snapshots
# are managed such that there are weekly snapshots of the past 5 weeks,
# monthly snapshots from the previous 6 months, and yearly snapshots until
# we run out of disk space.
#  
# The snapshots are labelled YYYY_MM_DD and are organized as follows:
# 
# mirror/weekly/
#             <week1>
#             <week2>
#             <week3>
#             <week4>
#             <week5>
# mirror/monthly/
#             <month1>
#             <month2>
#             <month3>
#             <month4>
#             <month5>
#             <month6>
# mirror/yearly/
#             <year1>
#             <year2>
#               ...
#
# Cron job will instigate a backup every week, doing the following:
# --- Create new backup weekly x
# --- Check if its a new month. If so, then copy week 1 to month y.
# --- Check if its a new year. If so, then copy month 1 to year z
# --- Delete weeklies to stay under 5 most recent weeks.
# --- Delete monthlies to stay under 12 most recent months.
#
# April 2017 v1
#
# Copyright (C) 2017 Patrick Schubert
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

from pathlib import Path
from datetime import datetime, timedelta
import myshutil as sh
import logging
import sys

SOURCE = '/media/otterback0/full'
DEST   = '/media/otterback1/mirror'
SANDBOX = Path('/media/otterback1/mirror')
WEEKLY_PATH = DEST / Path('weekly')
MONTHLY_PATH = DEST / Path('monthly')
YEARLY_PATH = DEST / Path('yearly')

# Max number of backups in each category.
MAX_WEEKLIES = 5
MAX_MONTHLIES = 6 

LOGFILE = '/home/otter/log/mirror.log'
LOGLEVEL = logging.DEBUG


class Backup:
    """Encapsulate a backup."""

    path = None
    date = None

    def __init__(self, path=None, date=None, parent=None):
        """Create a Backup.

        path - Path object pointing to location of backup.
        date - datetime object, date of backup.
        parent - parent directory of this backup.

        Backup dirname follows YYYY_MM_DD format.
        If path is supplied but not date, date will be generated automatically
        from the dir name.
        If date and parent are supplied but not path, path will be generated
        automatically.
        """
        self.path = path
        self.date = date
        if (date is None) and (path is not None):
            self.date = path_to_date(path)
        elif (path is None) and (date is not None) and (parent is not None):
            self.path = date_to_path(date, parent)
        return


def scan_existing(path):
    """Return the backups located within path.

    Ignores any file that fails path_to_date, i.e., subdirs must follow
    YYYY_MM_DD format.
    """
    backups = []
    for d in path.iterdir():
        if not d.is_dir():
            continue
        date = path_to_date(d)
        if date is None:
            continue
        backups.append(Backup(d, date))
    backups.sort(key=lambda x: x.path)
    return backups


def path_to_date(path):
    """Convert path to a date.

    Dir name must be in the format YYYY_MM_DD.
    """
    date = None
    try:
        path = path.name
        if (len(path) != 10):
            logging.error("path_to_date - bad length: {}".format(path))
            return None
        year = int(path[:4])
        month = int(path[5:7])
        day = int(path[8:])
        date = datetime(year, month, day)
    except:
        errStr = "path_to_date - some exception with dir [{0}]:{1}"
        logging.error(errStr.format(path, sys.exc_info()[0]))
    return date


def date_to_path(date, parent):
    """Convert a date to a dir name and tack that onto parent path."""
    dirname = '{:%Y_%m_%d}'.format(date)
    return parent / Path(dirname)


def MirrorBackup():
    """Mirror the backups.

    Performs the following actions:
         - Creates new backup in weeklies.
         - If new month, copies oldest weekly backup to monthly dir.
         - If new year, copies oldest monthly to yearly dir.
         - Prunes monthlies and weeklies to their limits.
    """

    global WEEKLY_PATH
    global MONTHLY_PATH
    global YEARLY_PATH
    global SANDBOX

    # Initialization
    logging.info("Started mirrorBackups {0}".format(datetime.now()))
    sh.set_sandbox(SANDBOX)

    WEEKLY_PATH = sh.standardize_path(WEEKLY_PATH)
    MONTHLY_PATH = sh.standardize_path(MONTHLY_PATH)
    YEARLY_PATH = sh.standardize_path(YEARLY_PATH)

    # Get the current set of backups
    weeklies = scan_existing(WEEKLY_PATH)
    monthlies = scan_existing(MONTHLY_PATH)
    yearlies = scan_existing(YEARLY_PATH)

    # Perfom backup. Copy from source to weekly dir.
    todaysBackup = Backup(date=datetime.today(), parent=WEEKLY_PATH)
    logging.info("Creating weekly backup {}".format(todaysBackup.path))
    ret = sh.copy(SOURCE, todaysBackup.path)
    if not ret:
        logging.error("Could not create weekly. Aborting.")
        sys.exit(1)

    # Check if this is a new month.
    # If so, then find the oldest and copy it to monthly.
    if (len(weeklies) > 0):
        prevWeek = weeklies[-1]
        if (prevWeek.date.month == todaysBackup.date.month):
            logging.debug("Same month.")
        else:
            logging.info("New month!")
            backupWeek = weeklies[0]
            for x in weeklies:
                # Find the oldest backup from the previous month. Due to months
                # being varying weeks long, weeklies[0] could be from two
                # months ago (ex: last week of january but today is first week
                # of march)
                if (x.date.month == prevWeek.date.month):
                    backupWeek = x
                    break
            logging.info("Creating new month {0}".format(backupWeek.path.name))
            ret = sh.copy(backupWeek.path, MONTHLY_PATH)
            if not ret:
                logging.error("Could not create monthly.")
                sys.exit(1)

    # Check if this is a new year.
    # If so, then find the oldest and copy it to yearly.
    if (len(monthlies) > 0):
        prevMonth = monthlies[-1]
        if (prevMonth.date.year == todaysBackup.date.year):
            logging.debug("Same year.")
        else:
            logging.info("New year!")
            backupMonth = monthlies[0]
            for x in monthlies:
                # Less likely than the week->month copy, but maybe monthlies[0]
                # is from two years ago (ex: December 2015 when today is
                # January 2017. Find the oldest backup from the previous year.
                if (x.date.year == prevMonth.date.year):
                    backupMonth = x
                    break
            logging.info("Creating new yearly {0}".format(
                                    backupMonth.path.name))
            ret = sh.copy(backupMonth, YEARLY_PATH)
            if not ret:
                logging.error("Could not create yearly.")
                sys.exit(1)

    # Prune weeklies. (MAX_WEEKLIES - 1 for today)
    while (len(weeklies) > MAX_WEEKLIES-1):
        excess_week = weeklies.pop(0)
        logging.info("Removing {0}".format(excess_week.path))
        ret = sh.rm(excess_week.path)
        if not ret:
            logging.error("rm weekly failed. Aborting prune.")
            sys.exit(1)

    # Prune monthlies. (MAX_MONTHLIES - 1 for today)
    while (len(monthlies) > MAX_MONTHLIES-1):
        excess_month = monthlies.pop(0)
        logging.info("Removing {0}".format(excess_month.path))
        ret = sh.rm(excess_month.path)
        if not ret:
            logging.error("rm monthly failed. Aborting prune.")
            sys.exit(1)

    return


if __name__ == "__main__":
    logging.basicConfig(format='[%(levelname)s %(module)s] %(message)s',
                        level=LOGLEVEL)
    MirrorBackup()
