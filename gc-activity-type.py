#!/usr/bin/python3
# -*- coding: utf-8 -*-
 
SCRIPT_VERSION = '0.0.5 (2021-03-31)'
"""
Original credits:
 
File: gcexport.py
Original author: Kyle Krafka (https://github.com/kjkjava/)
Date: April 28, 2015
Fork author: Michael P (https://github.com/moderation/)
Date: February 15, 2018
 
Description:    Use this script to export your fitness data from Garmin Connect.
                See README.md for more information.
 
Activity & event types:
    https://connect.garmin.com/modern/main/js/properties/event_types/event_types.properties
    https://connect.garmin.com/modern/main/js/properties/activity_types/activity_types.properties
"""
 
def show_exception_and_exit(exc_type, exc_value, tb):
    import traceback
    traceback.print_exception(exc_type, exc_value, tb)
    input("Press ENTER to exit.")
    sys.exit(-1)
 
import sys
sys.excepthook = show_exception_and_exit
 
# workaround for SSL certificate error
 
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
 
 
# ##############################################
 
from datetime import datetime, timedelta
from getpass import getpass
from os import mkdir, remove, stat
from os.path import isdir, isfile
from subprocess import call
from sys import argv
from xml.dom.minidom import parseString
 
import argparse
import http.cookiejar
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
 
#CURRENT_DATE = datetime.now().strftime('%Y-%m-%d')
#ACTIVITIES_DIRECTORY = './' + CURRENT_DATE + '_garmin_connect_export'
 
PARSER = argparse.ArgumentParser()
 
# TODO: Implement verbose and/or quiet options.
# PARSER.add_argument('-v', '--verbose', help="increase output verbosity", action="store_true")
PARSER.add_argument('--version', help="print version and exit", action="store_true")
PARSER.add_argument('--username', help="your Garmin Connect username (otherwise, you will be \
    prompted)", nargs='?')
PARSER.add_argument('--password', help="your Garmin Connect password (otherwise, you will be \
    prompted)", nargs='?')
 
PARSER.add_argument('--startdate', help="the date of the first activity to set to private (e.g. 2018-09-30) (otherwise, you will be \
    prompted)", nargs='?')
PARSER.add_argument('--enddate', help="the date of the last activity to set to private (e.g. 2018-10-30) (otherwise, you will be \
    prompted)", nargs='?')
 
PARSER.add_argument('--privacy', help="public, private, subscribers, groups", nargs='?')
 
PARSER.add_argument('--activity-type', '--activity_type', help="New activity type (default: 'cycling')")
PARSER.add_argument('--activity-type-id', '--activity_type_id', help="New activity type ID (default: 2)")
PARSER.add_argument('--activity-parent-type-id', '--activity_parent_type_id', help="New activity parent type ID (default: 17)")
 
PARSER.add_argument('--match-activity-type', '--match_activity_type', help="Existing activity type to match (e.g. 'running' or 'uncategorized') (default: all activity types are matched)")
PARSER.add_argument('--match-activity-type-id', '--match_activity_type_id', help="Existing activity type ID to match (e.g. '1') (default: all activity type IDs are matched)")
PARSER.add_argument('--match-activity-parent-type-id', '--match_activity_parent_type_id', help="Existing activity type ID to match (e.g. '17') (default: all activity parent type IDs are matched)")
 
PARSER.add_argument('--dry-run', '--dry_run', '--preview', help="preview changes (activities will not be modified)", action="store_true")
 
ARGS = PARSER.parse_args()
 
if ARGS.version:
    print(argv[0] + ", version " + SCRIPT_VERSION)
    exit(0)
 
if ARGS.dry_run:
    print('--dry-run specified. Activities will not be modified\n')
 
COOKIE_JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(COOKIE_JAR), urllib.request.HTTPSHandler(debuglevel=0))
# print(COOKIE_JAR)
 
 
# url is a string, post is the raw post data, headers is a dictionary of headers.
def http_req(url, post=None, headers=None):
    """Helper function that makes the HTTP requests."""
    request = urllib.request.Request(url)
    # Tell Garmin we're some supported browser.
    request.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, \
        like Gecko) Chrome/54.0.2816.0 Safari/537.36')
    if headers:
        for header_key, header_value in headers.items():
            request.add_header(header_key, header_value)
    if post:
        #post = urllib.parse.urlencode(post)
        post = post.encode('utf-8')  # Convert dictionary to POST parameter string.
    # print("request.headers: " + str(request.headers) + " COOKIE_JAR: " + str(COOKIE_JAR))
    # print("post: " + str(post) + "request: " + str(request))
    response = OPENER.open((request), data=post)
 
    if response.getcode() == 204:
        # For activities without GPS coordinates, there is no GPX download (204 = no content).
        # Write an empty file to prevent redownloading it.
        #print('Writing empty file since there was no GPX activity data...')
        return ''
    elif response.getcode() != 200:
        raise Exception('Bad return code (' + str(response.getcode()) + ') for: ' + url)
    # print(response.getcode())
 
    return response.read()
 
print('Welcome to the Garmin Connect Activity Type Tool!')
print('')
 
def promptGeneric(prompt, defaultValue, existingValue):
    if existingValue == None:
        INPUT = input('Enter ' + prompt + ': (default: ' + defaultValue + '): ')
        INPUT = INPUT.strip()
        if INPUT == '':
            INPUT = defaultValue
    else:
        INPUT = existingValue
 
    print('Selected ' + prompt + ': ' + str(INPUT))
 
    return INPUT
 
ACTIVITY_TYPE = ARGS.activity_type
ACTIVITY_TYPE_ID = ARGS.activity_type_id
ACTIVITY_PARENT_TYPE_ID = ARGS.activity_parent_type_id
 
DEFAULT_ACTIVITY_TYPE = 'cycling'
DEFAULT_ACTIVITY_TYPE_ID = '2'
DEFAULT_ACTIVITY_PARENT_TYPE_ID = '17'
 
ACTIVITY_TYPE = promptGeneric("new activity type", DEFAULT_ACTIVITY_TYPE, ACTIVITY_TYPE)
ACTIVITY_TYPE_ID = int(promptGeneric("new activity type ID", DEFAULT_ACTIVITY_TYPE_ID, ACTIVITY_TYPE_ID))
ACTIVITY_PARENT_TYPE_ID = int(promptGeneric("new activity parent type ID", DEFAULT_ACTIVITY_PARENT_TYPE_ID, ACTIVITY_PARENT_TYPE_ID))
print('')
if (not ARGS.match_activity_type == None):
    print(f'Matching activity type: {ARGS.match_activity_type}')
if (not ARGS.match_activity_type_id == None):
    ARGS.match_activity_type_id = int(ARGS.match_activity_type_id)
    print(f'Matching activity type ID: {ARGS.match_activity_type_id}')
if (not ARGS.match_activity_parent_type_id == None):
    ARGS.match_activity_parent_type_id = int(ARGS.match_activity_parent_type_id)
    print(f'Matching activity parent type ID: {ARGS.match_activity_parent_type_id}')
print('')
 
USERNAME=''
PASSWORD=''
while not USERNAME:
    USERNAME = ARGS.username if ARGS.username else input('Username: ')
    if not USERNAME:
        print("Please enter a username.")
        print("")
while not PASSWORD:
    PASSWORD = ARGS.password if ARGS.password else getpass()
    if not PASSWORD:
        print("Please enter a password.")
        print("")
 
# Maximum # of activities you can search for at once (URL_GC_LIST)
LIMIT_ACTIVITY_LIST = 5
 
print('Select Activities')
print('  Up to ' + str(LIMIT_ACTIVITY_LIST) + ' activities can be processed at one time.')
print('  Leave the start date blank to start at the beginning.')
print('  Leave the end date blank to end at the latest activity.')
print("")
 
def promptDate(prompt, defaultValue, errorStr):
    while True:
        DATE = defaultValue if defaultValue else input(prompt)
        DATE = DATE.strip()
        if not DATE:
            break;
        try:
            datetime.strptime(DATE, '%Y-%m-%d')
        except ValueError:
            #raise ValueError("Incorrect data format, should be YYYY-MM-DD")
            print(errorStr)
            print("")
            continue
        break
    return DATE
 
STARTDATE = promptDate('  Start Date (e.g. "2018-09-30" or blank): ', ARGS.startdate, "  Invalid date.")
ENDDATE = promptDate('  End Date (e.g. "2018-10-30" or blank): ', ARGS.enddate, "  Invalid date.")
print('')
 
# Maximum number of activities you can request at once.  Set and enforced by Garmin.
LIMIT_MAXIMUM = 1000
 
WEBHOST = "https://connect.garmin.com"
REDIRECT = "https://connect.garmin.com/modern/"
BASE_URL = "https://connect.garmin.com/en-US/signin"
SSO = "https://sso.garmin.com/sso"
CSS = "https://static.garmincdn.com/com.garmin.connect/ui/css/gauth-custom-v1.2-min.css"
 
DATA = {
    'service': REDIRECT,
    'webhost': WEBHOST,
    'source': BASE_URL,
    'redirectAfterAccountLoginUrl': REDIRECT,
    'redirectAfterAccountCreationUrl': REDIRECT,
    'gauthHost': SSO,
    'locale': 'en_US',
    'id': 'gauth-widget',
    'cssUrl': CSS,
    'clientId': 'GarminConnect',
    'rememberMeShown': 'true',
    'rememberMeChecked': 'false',
    'createAccountShown': 'true',
    'openCreateAccount': 'false',
    'usernameShown': 'false',
    'displayNameShown': 'false',
    'consumeServiceTicket': 'false',
    'initialFocus': 'true',
    'embedWidget': 'false',
    'generateExtraServiceTicket': 'true',
    'generateTwoExtraServiceTickets': 'false',
    'generateNoServiceTicket': 'false',
    'globalOptInShown': 'true',
    'globalOptInChecked': 'false',
    'mobile': 'false',
    'connectLegalTerms': 'true',
    'locationPromptShown': 'true',
    'showPassword': 'true'    
}
 
#print(urllib.parse.urlencode(DATA))
 
# URLs for various services.
URL_GC_LOGIN = 'https://sso.garmin.com/sso/signin?' + urllib.parse.urlencode(DATA)
URL_GC_POST_AUTH = 'https://connect.garmin.com/modern/activities?'
URL_GC_SEARCH = 'https://connect.garmin.com/proxy/activity-search-service-1.2/json/activities?'
URL_GC_LIST = \
    'https://connect.garmin.com/modern/proxy/activitylist-service/activities/search/activities?'
URL_GC_ACTIVITY = 'https://connect.garmin.com/modern/proxy/activity-service/activity/'
URL_GC_ACTIVITY_DETAIL = \
    'https://connect.garmin.com/modern/proxy/activity-service-1.3/json/activityDetails/'
URL_GC_GPX_ACTIVITY = \
    'https://connect.garmin.com/modern/proxy/download-serviceOther25/export/gpx/activity/'
URL_GC_TCX_ACTIVITY = \
    'https://connect.garmin.com/modern/proxy/download-service/export/tcx/activity/'
URL_GC_ORIGINAL_ACTIVITY = 'http://connect.garmin.com/proxy/download-service/files/activity/'
 
URL_GC_ACTIVITY_PAGE = 'https://connect.garmin.com/modern/activity/'
 
print("Logging in...")
 
# Initially, we need to get a valid session cookie, so we pull the login page.
#print('Request login page')
connect_response = http_req(URL_GC_LOGIN)
# write_to_file('connect_response.html', connect_response, 'w')
#for cookie in COOKIE_JAR:
#   logging.debug("Cookie %s : %s", cookie.name, cookie.value)
#print('Finish login page')
 
# Now we'll actually login.
# Fields that are passed in a typical Garmin login.
POST_DATA = {
    'username': USERNAME,
    'password': PASSWORD,
    'embed': 'false',
    'rememberme': 'on'
    }
    
headers = {
    'referer': URL_GC_LOGIN
}    
 
#print('Post login data')
LOGIN_RESPONSE = http_req(URL_GC_LOGIN + '#', urllib.parse.urlencode(POST_DATA), headers).decode()
#print('Finish login post')
 
# extract the ticket from the login response
PATTERN = re.compile(r".*\?ticket=([-\w]+)\";.*", re.MULTILINE|re.DOTALL)
MATCH = PATTERN.match(LOGIN_RESPONSE)
if not MATCH:
    raise Exception('Did not get a ticket in the login response. Cannot log in. Did \
you enter the correct username and password?')
LOGIN_TICKET = MATCH.group(1)
#print('login ticket=' + LOGIN_TICKET)
 
#print("Request authentication URL: " + URL_GC_POST_AUTH + 'ticket=' + LOGIN_TICKET)
#print("Request authentication")
LOGIN_AUTH_REP = http_req(URL_GC_POST_AUTH + 'ticket=' + LOGIN_TICKET).decode()
#print(LOGIN_AUTH_REP)
#print('Finished authentication')
 
 
SEARCH_PARAMS = {'start': 0, 'limit': LIMIT_ACTIVITY_LIST}
 
if STARTDATE:
    SEARCH_PARAMS['startDate'] = STARTDATE
if ENDDATE:
    SEARCH_PARAMS['endDate'] = ENDDATE
 
ACLISTURL = URL_GC_LIST + urllib.parse.urlencode(SEARCH_PARAMS)
#print("Activity list URL: " + ACLISTURL)
 
print('')
print('Searching for activities (this might take a while)...')
print('')
#print('Loading activity list')
ACTIVITY_LIST = http_req(ACLISTURL, None, {
    'NK': 'NT'
})
 
#print('Processing activity list')
#print('')
 
JSON_LIST = json.loads(ACTIVITY_LIST)
 
if len(JSON_LIST) == 0:
    print("No activities found for the given date range.")
else:
    print("Found " + str(len(JSON_LIST)) + " activities.")
 
for a in JSON_LIST:
    print(f'Activity: {a["startTimeLocal"]} | {a["activityName"] if a["activityName"] else ""} | Type: {a["activityType"]["typeKey"]} (typeId: {a["activityType"]["typeId"]}, parentTypeId: {a["activityType"]["parentTypeId"]})')
 
    if (not ARGS.match_activity_type == None):
        if ARGS.match_activity_type == a["activityType"]["typeKey"]:
            print(f'  Matched activity type: {ARGS.match_activity_type}')
        else:
            print(f'  Did not match activity type: {ARGS.match_activity_type}')
            print('  Skipping activity')
            continue
    if (not ARGS.match_activity_type_id == None):
        if ARGS.match_activity_type_id == a["activityType"]["typeId"]:
            print(f'  Matched activity type ID: {str(ARGS.match_activity_type_id)}')
        else:
            print(f'  Did not match activity type ID: {str(ARGS.match_activity_type_id)}')
            print('  Skipping activity')
            continue
    if (not ARGS.match_activity_parent_type_id == None):
        if ARGS.match_activity_parent_type_id == a["activityType"]["parentTypeId"]:
            print(f'  Matched activity parent type ID: {str(ARGS.match_activity_parent_type_id)}')
        else:
            print(f'  Did not match activity parent type ID: {str(ARGS.match_activity_parent_type_id)}')
            print('  Skipping activity')
            continue
 
    newActivityType = f'{ACTIVITY_TYPE} (typeId: {str(ACTIVITY_TYPE_ID)}, parentTypeId: {str(ACTIVITY_PARENT_TYPE_ID)})'
    if (ARGS.dry_run):
        print('  (Dry run) would have set activity type to ' + newActivityType)
        continue
    else:
        print('  Setting activity type to ' + newActivityType)
 
    ACTIVITY_URL = URL_GC_ACTIVITY + str(a['activityId'])
    ACTIVITY_PAGE_URL = URL_GC_ACTIVITY_PAGE + str(a['activityId'])
    ACTIVITY_POST_DATA = {'activityTypeDTO': {'typeId': ACTIVITY_TYPE_ID, 'typeKey': ACTIVITY_TYPE, 'parentTypeId': ACTIVITY_PARENT_TYPE_ID}, 'activityId': a['activityId'] }
    ACTIVITY_POST_HEADERS = {
        'referer': ACTIVITY_PAGE_URL, 
        'authority': 'connect.garmin.com', 
        'origin': 'https://connect.garmin.com', 
        'Content-Type':'application/json', 
        'X-HTTP-Method-Override': 'PUT', 
        'X-Requested-With': 'XMLHttpRequest', 
        'nk': 'NT'
    }
    http_req(ACTIVITY_URL, json.dumps(ACTIVITY_POST_DATA), ACTIVITY_POST_HEADERS)
 
print('')
print('Done!')
 
input('Press ENTER to quit');