#!/bin/python

#Author: Marcus Hanikat (hanikat@kth.se)
#Tested with Nagios 4.4.5 on Ubuntu

#Arguments:
#1: $SERVICESTATE$
#2: $SERVICESTATETYPE$
#3: $HOSTNAME$
#4: $SERVICEDISPLAYNAME$
#5: $SERVICEPERCENTCHANGE$
#6: $LONGSERVICEOUTPUT$
#7: $HOSTADDRESS$
#8: $HOSTGROUPNOTES$
#9: $SERVICENOTES$
#10: $SERVICEPROBLEMID$

import argparse
import subprocess
from datetime import datetime

# ----- ARGUMENT PARSING ----- #
parser = argparse.ArgumentParser()
parser.add_argument("SERVICESTATE", help="Nagios macro for current service state (OK, WARNING, UNKNOWN, CRITICAL).")
parser.add_argument("SERVICESTATETYPE", help="Nagios macro for current service state type (HARD, SOFT).")
parser.add_argument("HOSTNAME", help="Nagios macro for host name which the service belongs to.")
parser.add_argument("SERVICEDISPLAYNAME", help="Nagios macro for the service display name.")
parser.add_argument("SERVICEPERCENTCHANGE", help="Nagios macro for getting the flapping percentage of the service.")
parser.add_argument("LONGSERVICEOUTPUT", help="Nagios macro for getting the service error message.")
parser.add_argument("HOSTADDRESS", help="Nagios macro for getting the IP-address of the host which the service belongs to.")
parser.add_argument("HOSTGROUPNOTES", help="Nagios macro for getting the notes belonging to the host group which the service and host belongs to.")
parser.add_argument("SERVICENOTES", help="Nagios macro for getting the notes belonging to the specific service.")
parser.add_argument("SERVICEPROBLEMID", help="Nagios macro for getting the unique problem id associated with the service problem state.")
args = parser.parse_args()

# ----- VARIABLE DEFINITIONS ----- #
DEBUG = False
#File locations
logFile = ""
#ackFile can be used to store the "Problem ID" of a service when it is acknowledge, this will not send an mail for all acknowledged problems within this file
ackFile = ""
#exclFile can be used to store strings on sepearte lines which if present in the service description during problems will cause the script to not send an mail
exclFile = ""
#Define flap threshold for when a service is considered flapping
flapThreshold = 35
#Mail addresses
sendToMail = ""
sendToMail_DEBUG = ""
fromMailAddress = ""

# argument debug
if(DEBUG):
        with open(logFile, 'a') as the_file:
                the_file.write("***** " + str((datetime.now().strftime("%d/%m/%Y %H:%M:%S")) + " *****"))
                the_file.write('Script called with following arguments: \n')
                the_file.write("SERVICESTATE: " + str(args.SERVICESTATE) + "\n")
                the_file.write("SERVICESTATETYPE: " + str(args.SERVICESTATETYPE) + "\n")
                the_file.write("HOSTNAME: " + str(args.HOSTNAME) + "\n")
                the_file.write("SERVICEDISPLAYNAME: " + str(args.SERVICEDISPLAYNAME) + "\n")
                the_file.write("SERVICEPERCENTAGECHANGE: " + str(args.SERVICEPERCENTCHANGE) + "\n")
                the_file.write("LONGSERVICEOUTPUT: " + str(args.LONGSERVICEOUTPUT) + "\n")
                the_file.write("HOSTADDRESS: " + str(args.HOSTADDRESS) + "\n")
                the_file.write("HOSTGROUPNOTES: " + str(args.HOSTGROUPNOTES) + "\n")
                the_file.write("SERVICENOTES: " + str(args.SERVICENOTES) + "\n")
                the_file.write("SERVIEPROBLEMID: " + str(args.SERVICEPROBLEMID) + "\n")

# ----- FUNCTION DEFINITIONS ----- #

#Define function for checking if the service have been acknowledged
def is_acknowledge(problemid):

        #Open and read acknowledgement file
        acknowledgements = open(ackFile, 'r')
        ackList = acknowledgements.readlines()
        acknowledgements.close()

        #Search file for acknowledgement of the current problem
        found = False
        for line in ackList:
                if(str(problemid) in line):
                        found = True
                        break

        #Return result of search
        return found

#Define function for checking if the service is in a flapping state
def is_flapping(flapPercent):
        if(float(flapPercent) > float(flapThreshold)):
                return True
        else:
                return False

#Define function for checking if the service is in exclusion list of services not to be automatically converted to cases
def is_excluded(serviceOutput):

        #Open and read acknowledget file
        exclusions = open(exclFile, 'r')
        exclList = exclusions.readlines()
        exclusions.close()

        #Search file for exclusion strings and see if they match the service output text
        found = False
        for lines in exclList:
                line = lines.splitlines()[0]
                if(str(line) in str(serviceOutput) and line != ""):
                        found = True
                        break

        #Return result of search
        return found

#Define function for formatting and sending an email
def create_case():
        body = ("***** Nagios ***** \n\n" +
                "Host: " + str(args.HOSTNAME) + "\n" +
                "Service: " + str(args.SERVICEDISPLAYNAME) + "\n" +
                "Description: " + str(args.LONGSERVICEOUTPUT) + "\n" +
                "Address: " + str(args.HOSTADDRESS) + "\n" +
                "Date/Time: " + str(datetime.now().strftime("%d/%m/%Y %H:%M:%S")) + "\n\n" +
                "Parameters: " + str(args.HOSTGROUPNOTES) + ", " + str(args.SERVICENOTES))

        subject = '-s \"Nagios: Service Alert on host: ' + str(args.HOSTNAME) + '\"'

        first = subprocess.Popen(['/usr/bin/printf', body], stdout=subprocess.PIPE)
        subject = '-s Nagios: Service Alert on host: ' + str(args.HOSTNAME)
        subprocess.Popen(['/usr/bin/mail', '-aFrom:' + fromMailAddress, subject, sendToMail], stdin=first.stdout)
        if(DEBUG):
                print("Case created!")
                first = subprocess.Popen(['/usr/bin/printf', body], stdout=subprocess.PIPE)
                subprocess.Popen(['/usr/bin/mail', '-aFrom:' + fromMailAddress, subject, sendToMail_DEBUG], stdin=first.stdout)
        with open(logFile, 'a') as log_file:
                log_file.write(str(datetime.now().strftime(("%d/%m/%Y %H:%M:%S")) + 'Case Created with Problem ID: ' + str(args.SERVICEPROBLEMID) + '\n'))

# ----- PROGRAM EXECUTION ----- #

# Check what state the service is in
if(args.SERVICESTATE == "OK"):
        if(DEBUG):
                print("Service State: OK")
elif(args.SERVICESTATE == "WARNING"):
        # Service is in warning state, check if the service in a hard state type or not
        if(args.SERVICESTATETYPE == "HARD"):
                # Service is in HARD state type, check if the service is flapping
                if(not is_flapping(args.SERVICEPERCENTCHANGE)):
                        # The service is not flapping, check if it has been acknowledge
                                if(not is_acknowledge(args.SERVICEPROBLEMID)):
                                        # The service has not been acknowledge, chekc if it is in the exclusion list
                                        if(not is_excluded(args.LONGSERVICEOUTPUT)):
                                                # The service is not in exclusion list, send an mail in order to create a new case
                                                create_case()
                                        else:
                                                if(DEBUG):
                                                        print("Service excluded!")
                                else:
                                        if(DEBUG):
                                                print("Service acknowledge!")
elif(args.SERVICESTATE == "UNKNOWN"):
        if(DEBUG):
                print("Service State: UNKNOWN")
elif(args.SERVICESTATE == "CRITICAL"):
         # Service is in critical state, check if the service in a hard state type or not
        if(args.SERVICESTATETYPE == "HARD"):
                # Service is in HARD state type, check if the service is flapping
                if(not is_flapping(args.SERVICEPERCENTCHANGE)):
                        # The service is not flapping, check if it has been acknowledge
                        if(not is_acknowledge(args.SERVICEPROBLEMID)):
                                # The service has not been acknowledge, chekc if it is in the exclusion list
                                if(not is_excluded(args.LONGSERVICEOUTPUT)):
                                        # The service is not in exclusion list, send an mail in order to create a new case
                                        create_case()
                                else:
                                        if(DEBUG):
                                                print("Service is excluded! (CRITICAL)")
                        else:
                                if(DEBUG):
                                        print("Service is acknowledge! (CRITICAL)")
                else:
                        if(DEBUG):
                                print("Service is flapping (CRITICAL)")
