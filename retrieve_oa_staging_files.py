#search for conversion.ok or conversion.error.  If conversion.error, put in log
#need to pull date from those csv files.  look in emails for link
#don't bother copying the files in this case
#match fields in both files (match order if possible)
#use appidnotfound and nofilefound logs to determine which files to pull
#DocumentIdentifier is equal to ifwnum
#DocumentCode = documentsourceidentifier
#OfficeActionTypeCode = DocumentCode
#GroupArtUnitNumber
#PartyIdentifier
#name XML file and OACSConversion file with app ID and IFW num like other directory

#!/usr/bin/env python 3.5

#Author:        Sasan Bahadaran
#Date:          6/27/16
#Organization:  Commerce Data Service
#Description:   This script crawls specific directory structures of Office Action
#files, renames them with app ID and IFW number, parses the XML, combines the XML
#with PALM data from flat files, and gets the post date from a CMS RESTFUL service.
#It then transforms the resulting dictionary to JSON and sends it to Solr for indexing.

import sys, os, glob, shutil, logging, time, argparse, glob, json, requests,\
csv, collections, math

from datetime import datetime
from lxml import etree
import pandas as pd

#get public app IDs from app ID file
def getAppIDs(fname):
    try:
        with open(os.path.abspath(fname)) as fd:
            for line in fd:
                if line.startswith(series):
                    appids.append(line.strip())
        logging.info("-- Number of appids for this series: "+str(len(appids)))
    except IOError as e:
         logging.error('-- Get App IDs I/O error({0}): {1}'.format(e.errno,e.strerror))

#construct app ID file path from app ID
def constructPath(appid):
    fileurl = oafilespath+'\\'+appid[:2]+'\\'+appid[2:5]+'\\'+appid[5:8]
    return fileurl

#create directory if it does not exist
def makeDirectory(directory):
    if not os.path.isdir(directory):
        os.makedirs(directory)
        logging.info('-- Directory: '+directory+' created')
        print('directory created!!!!!')

#split path to get app ID
def splitAll(path):
    allparts = []
    while 1:
        parts = os.path.split(path)
        if parts[0] == path:  # sentinel for absolute paths
            allparts.insert(0, parts[0])
            break
        elif parts[1] == path: # sentinel for relative paths
            allparts.insert(0, parts[1])
            break
        else:
            path = parts[0]
            allparts.insert(0, parts[1])
    return allparts

#construct file name from app ID, ifw number, and original name
def constructFilename(fname, appid, ifwnum):
    fpath,filename = os.path.split(fname)
    filename = os.path.splitext(filename)[0]
    filename = filename.replace(" ", "_").replace("'", "")
    selparts = (appid,ifwnum,filename)
    newfname = os.path.join(scriptpath, 'extractedfiles', series, 'staging', '_'.join(selparts)+'.xml')
    #change this to just filename instead of full path since it will just be copied to s3
    return newfname

#copy extracted file to central directory
def copyFile(old,new):
    try:
        fpath, fname = os.path.split(new)
        if not os.path.isfile(new):
            shutil.copyfile(old,new)
            logging.info("-- File: "+fname+" written to directory: "+fpath)
            completeappids.append(currentapp)
        else:
            logging.info("-- File: "+fname+" already exists")
    except IOError as e:
         logging.error('-- Copy File I/O error({0}): {1}'.format(e.errno,e.strerror))

#write list of app ID's to specified log file
def writeLogs(logfname,idlist):
    try:
        with open(logfname,'a+') as logfile:
            for appid in idlist:
                logfile.write(appid+"\n")
        logging.info('-- Log entries for: '+logfname+' written to file')
    except IOError as e:
        logging.error('-- Write Log: '+logfname+' I/O error({0}): {1}'.format(e.errno,e.strerror))

#change extension of file name to specified extension
def changeExt(fname, ext):
    seq = (os.path.splitext(fname)[0], ext)
    return '.'.join(seq)

def getIFWNum(fname):
    try:
        parser = etree.XMLParser(remove_pis=True)
        tree = etree.parse(fname, parser=parser)
        root = tree.getroot()
        namespaces = {'uscom':'urn:us:gov:doc:uspto:common'}
        for item in root.xpath('//uscom:Document', namespaces=namespaces):
            return item.find('uscom:DocumentIdentifier', namespaces=namespaces).text
    except IOError as e:
        logging.error('XML Parse file: '+fname+' I/O error({0}): {1}'.format(e.errno,e.strerror))
        return ''
    except etree.XMLSyntaxError:
        logging.error('-- Skipping invalid XML from file: '+fname)
        badfiles.append(fname)
        return False

#get metadata and text from P tags in XML document
def getText(node):
    contents = ''
    if node.tag == '{urn:us:gov:doc:uspto:common}LI' and node.text is not None:
        contents += (node.get('{http://www.wipo.int/standards/XMLSchema/ST96/Common}liNumber')+' '+node.text +
                     ''.join(map(getText, node)) +
                     (node.tail or ''))
    #ignore data table text
    elif node.tag == '{urn:us:gov:doc:uspto:common}DataTable':
        return contents
    #ignore image paragraphs
    elif node.tag == '{http://www.wipo.int/standards/XMLSchema/ST96/Common}Image':
        return contents
    else:
        contents += ((node.text or '') +
                    ''.join(map(getText, node)) +
                    (node.tail or ''))
    return contents

#code for parsing XML file
def parseXML(fname):
    try:
        textdata = ''
        parser = etree.XMLParser(remove_pis=True)
        tree = etree.parse(fname, parser=parser)
        root = tree.getroot()
        namespaces = {'uspat':'urn:us:gov:doc:uspto:patent',
                      'uscom':'urn:us:gov:doc:uspto:common',
                      'com':'http://www.wipo.int/standards/XMLSchema/ST96/Common'}
        for item in root.xpath('//uspat:DocumentMetadata', namespaces=namespaces):
            doccontent['documentcode'] = item.find('uscom:DocumentCode', namespaces=namespaces).text
            doccontent['documentsourceidentifier'] = item.find('uscom:DocumentSourceIdentifier', namespaces=namespaces).text
            partyid = doccontent['partyidentifier'] = item.find('com:PartyIdentifier', namespaces=namespaces)
            if partyid is not None:
                doccontent['partyidentifier'] = partyid.text
            else:
                doccontent['partyidentifier'] = ''
            doccontent['groupartunitnumber'] = item.find('uscom:GroupArtUnitNumber', namespaces = namespaces).text
        for item in root.xpath('//uscom:P', namespaces=namespaces):
            textdata += getText(item)+'\n'
        doccontent['textdata'] = textdata
        return True
    except IOError as e:
        logging.error('XML Parse file: '+fname+' I/O error({0}): {1}'.format(e.errno,e.strerror))
        return False
    except etree.XMLSyntaxError:
        logging.error('-- Skipping invalid XML from file: '+fname)
        badfiles.append(fname)
        return False

#convert day-month-year to UTC timestamp
def convertToUTC(date,format):
    if date != '' and date != None:
        dt = datetime.strptime(date, format)
        dt = time.mktime(dt.timetuple())
    else:
        dt = ''
    return dt

# #deal with na values and set type as string
# def fixNaValues(dataframe,series):
#     for col in series:
#         values[col] = values[col].fillna('')
#         values[col] = values[col].astype('str')
#
# #code for extracting PALM data from PALM series file and combine with other elements from XML file
# def getPALMData(fileappid):
#     try:
#         logging.info('-- Starting PALM data match process')
#         values = df[(df['APPL_ID'] == float(fileappid))]
#         series = ['FILE_DT','EFFECTIVE_FILING_DT','ABANDON_DT','DN_NSRD_CURR_LOC_DT',\
#         'APP_STATUS_DT','PATENT_ISSUE_DT','ABANDON_DT']
#         fixNaValues(values, series)
#         if len(values.index) == 1:
#             for index, row in values.iterrows():
#                 doccontent['appl_id'] = row.APPL_ID
#                 doccontent['file_dt'] = convertToUTC(row.FILE_DT, '%d-%b-%y')
#                 doccontent['effective_filing_dt'] = convertToUTC(row.EFFECTIVE_FILING_DT, '%d-%b-%y')
#                 doccontent['inv_subj_matter_ty'] = row.INV_SUBJ_MATTER_TY
#                 doccontent['appl_ty'] = row.APPL_TY
#                 doccontent['dn_examiner_no'] = row.DN_EXAMINER_NO
#                 doccontent['dn_dw_dn_gau_cd'] = row.DN_DW_DN_GAU_CD
#                 doccontent['dn_pto_art_class_no'] = row.DN_PTO_ART_CLASS_NO
#                 doccontent['dn_pto_art_subclass_no'] = row.DN_PTO_ART_SUBCLASS_NO
#                 doccontent['confirm_no'] = row.CONFIRM_NO
#                 doccontent['dn_intppty_cust_no'] = row.DN_INTPPTY_CUST_NO
#                 doccontent['atty_dkt_no'] = row.ATTY_DKT_NO
#                 doccontent['dn_nsrd_curr_loc_cd'] = row.DN_NSRD_CURR_LOC_CD
#                 doccontent['dn_nsrd_curr_loc_dt'] = convertToUTC(row.DN_NSRD_CURR_LOC_DT, '%d-%b-%y')
#                 doccontent['app_status_no'] = row.APP_STATUS_NO
#                 doccontent['app_status_dt'] = convertToUTC(row.APP_STATUS_DT, '%d-%b-%y')
#                 doccontent['wipo_pub_no'] = row.WIPO_PUB_NO
#                 doccontent['patent_no'] = row.PATENT_NO
#                 doccontent['patent_issue_dt'] = convertToUTC(row.PATENT_ISSUE_DT, '%d-%b-%y')
#                 doccontent['abandon_dt'] = convertToUTC(row.ABANDON_DT, '%d-%b-%y')
#                 doccontent['disposal_type'] = row.DISPOSAL_TYPE
#                 doccontent['se_in'] = row.SE_IN
#                 doccontent['pct_no'] = row.PCT_NO
#                 doccontent['invn_ttl_tx'] = row.INVN_TTL_TX
#                 doccontent['aia_in'] = row.AIA_IN
#                 doccontent['continuity_type'] = row.CONTINUITY_TYPE
#                 doccontent['frgn_priority_clm'] = row.FRGN_PRIORITY_CLM
#                 doccontent['usc_119_met'] = row.USC_119_MET
#                 doccontent['fig_qt'] = row.FIG_QT
#                 doccontent['indp_claim_qt'] = row.INDP_CLAIM_QT
#                 doccontent['efctv_claims_qt'] = row.EFCTV_CLAIMS_QT
#                 logging.info('-- PALM data written to doccontent dictionary')
#                 return True
#         else:
#             logging.error('-- Application ID: '+fileappid+' not found in PALM data')
#             notfoundPALM.append(fileappid)
#             return False
#     except IOError as e:
#         logging.error('PALM Extract file: '+fileappid+' I/O error({0}): {1}'.format(e.errno,e.strerror))
#         return False

#get official application doc date
def getDocDate(appid, ifwnum):
    try:
        params = [{"businessUnitId": appid,
              "documentId": ifwnum}]
        headers = {'Content-type': 'application/json'}
        response = requests.post(cmsURL, json=params, headers=headers)
        r = response.json()
        if 'httpStatus' in r:
            doc_date = ''
            logging.info('-- App ID: '+appid+', IFW#: '+ifwnum+' not found from CMS service')
            notfoundCMS.append(appid+', '+ifwnum)
        elif 'officialDocumentDate' in r[0]:
            doc_date = convertToUTC(r[0]['officialDocumentDate'], '%Y-%m-%d')
        doccontent['doc_date'] = doc_date
        return True
    except requests.exceptions.RequestException as e:
        logging.error('-- CMS Restful error for: '+appid+', '+ifwnum+', error: '+e)
        notfoundCMS.append(appid+', '+ifwnum)
        return False

#write dictionary to JSON file
def writeToJSON(fname):
    try:
        with open(fname,'w') as outfile:
            json.dump(doccontent,outfile)
            logging.info('-- File written to : '+fname)
            return True
    except IOError as e:
        logging.error('Write to JSON: '+fname+' I/O error({0}): {1}'.format(e.errno,e.strerror))
        return False

#read JSON file and set up for sending to Solr
def readJSON(fname):
    try:
        docid = fname.split('_')[0]+', '+fname.split('_')[1]
        with open(fname, 'r') as fd:
            jsontext = json.load(fd)
            with open(os.path.join(os.path.dirname(fname), 'solrComplete.log'), 'a+') as logfile:
                logfile.seek(0)
                if docid+'\n' in logfile:
                    logging.info('-- File: '+docid+' already processed by Solr')
                else:
                    logging.info('-- Sending file: '+docid+' to Solr')
                    response = sendToSolr('oa', jsontext)
                    r = response.json()
                    status = r['responseHeader']['status']
                    if status == 0:
                        logfile.write(docid+"\n")
                        logging.info("-- Solr update for file: "+docid+" complete")
                    else:
                        logging.info("-- Solr error for doc: "+docid+" error: "+', '.join("{!s}={!r}".format(k,v) for (k,v) in rdict.items()))
    except IOError as e:
        logging.error('Read JSON file: '+fname+' I/O error({0}): {1}'.format(e.errno,e.strerror))
    except:
        logging.error('Unexpected error:', sys.exc_info()[0])
        raise

#send document to Solr for indexin
def sendToSolr(core, json):
    try:
        jsontext = '{"add":{ "doc":'+json+',"boost":1.0,"overwrite":true, "commitWithin": 1000}}'
        url = os.path.join(solrURL,"solr",core,"update")
        headers = {"Content-type" : "application/json"}
        return requests.post(url, data=jsontext, headers=headers)
    except requests.exceptions.RequestException as e:
        logging.error('-- Solr indexing error: '+e)

if __name__ == '__main__':
    scriptpath = os.path.dirname(os.path.abspath(__file__))
    appnotfoundfname = 'appnotfound.log'
    nofilefoundfname = 'nofilefound.log'
    notfoundpalmfname = 'notfoundPALM.log'
    oafilespath = '\\\\s-mdw-isl-b02-smb.uspto.gov\\BigData\\BackFile'
    #cmsURL = 'http://p-elp-services.uspto.gov/cmsservice/pto/PATENT/documentMetadataByAccess'
    solrURL = ''
    appids = []
    completeappids = []
    notfoundappids = []
    nofileappids = []
    notfoundPALM = []
    notfoundCMS = [] #records appid and ifw number
    badfiles = []
    currentapp = ''
    numoffileswritten = 0
    doccontent = collections.OrderedDict()
    ifwnum = ''

    #logging configuration
    logging.basicConfig(
                        filename='logs/extract-staging-files-log-'+time.strftime('%Y%m%d')+'.txt',
                        level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s -%(message)s',
                        datefmt='%Y%m%d %H:%M:%S'
                       )
    parser = argparse.ArgumentParser()
    parser.add_argument(
                        '-s',
                        '--series',
                        required=True,
                        help='Specify series to process - format ## (separate each additional series with space)',
                        nargs='*',
                        type=str
                       )
    parser.add_argument(
                        '-e',
                        '--skipextraction',
                        required=False,
                        help='Pass this flag to skip File extraction',
                        action='store_true'
                       )
    parser.add_argument(
                        '-p',
                        '--skipparsing',
                        required=False,
                        help='Pass this flag to skip File parsing',
                        action='store_true'
                       )
    parser.add_argument(
                        '-i',
                        '--skipsolr',
                        required=False,
                        help='Pass this flag to skip Solr indexing',
                        action='store_true'
                       )
    args = parser.parse_args()
    logging.info("-- SCRIPT ARGUMENTS ------------")
    if args.series:
        logging.info("-- Series passed for processing: "+", ".join(args.series))
    logging.info("-- Skip Extraction flag set to: "+str(args.skipextraction))
    logging.info("-- Skip Parsing flag set to: "+str(args.skipparsing))
    logging.info("-- Skip Solr flag set to: "+str(args.skipsolr))
    logging.info("-- [JOB START]  ----------------")

    for series in args.series:
        seriespath = os.path.join(scriptpath,'extractedfiles', series, 'staging')
        print("seriespath: "+seriespath)
        if not args.skipextraction:
            logging.info("-- Processing series: "+series)
            getAppIDs(os.path.join(scriptpath, 'extractedfiles', series, appnotfoundfname))
            getAppIDs(os.path.join(scriptpath, 'extractedfiles', series, nofilefoundfname))
            getAppIDs(os.path.join(scriptpath, 'extractedfiles', series, notfoundpalmfname))
            makeDirectory(os.path.join(scriptpath, 'extractedfiles', series, 'staging'))
            for x in appids:
                try:
                    currentapp = x
                    logging.info('-- Searching for app ID: '+currentapp)
                    seriesdirpath = constructPath(x)
                    print("seriesdirpath: "+seriesdirpath)
                    if os.path.isdir(seriesdirpath):
                        donotprocess = False
                        dirfiles = {}
                        for dirname in glob.glob(os.path.join(seriesdirpath, '*')):
                            print("dirname: "+dirname)
                            if os.path.isfile(os.path.join(dirname,'conversion.ok')):
                                print("conversion.ok file found")
                                for name in glob.glob(os.path.join(dirname, '*.DOCM')):
                                    print("DOCM: "+name)
                                    fn = changeExt(name, 'xml')
                                    if os.path.isfile(fn):
                                        convfn = os.path.join(dirname, 'OACSConversion.xml')
                                        if os.path.isfile(convfn):
                                            ifwnum = getIFWNum(convfn)
                                            newfn = constructFilename(fn, currentapp, ifwnum)
                                            logging.info("-- New file name: "+newfn)
                                            dirfiles[fn] = newfn
                                            newconvfn = constructFilename(convfn, currentapp, ifwnum)
                                            logging.info('-- New Conversion file name: '+newconvfn)
                                            dirfiles[convfn] = newconvfn
                                    else:
                                        print("XML file not found")
                                        logging.info("-- XML file not found for: "+name)
                                        donotprocess = True
                            else:
                                print("conversion.ok file not found!")
                                donotprocess = True
                        if donotprocess == False:
                            #for each file, run copy
                            for k, v in dirfiles.items():
                                copyFile(k, v)
                        else:
                            logging.info('-- One of the files for app ID: '+currentapp+' not found')
                            nofileappids.append(currentapp)
                    else:
                        logging.info("-- App ID: "+currentapp+" not found")
                        notfoundappids.append(currentapp)
                    currentapp = ''
                except IOError as e:
                    logging.error('-- Extraction file: '+' I/O error({0}): {1}'.format(e.errno,e.strerror))
                except:
                    logging.error('-- Unexpected error:', sys.exc_info()[0])
                    raise
            writeLogs(os.path.join(seriespath,'appcomplete.log'),completeappids)
            writeLogs(os.path.join(seriespath,'appnotfound.log'),notfoundappids)
            writeLogs(os.path.join(seriespath,'nofilefound.log'),nofileappids)
            #empty lists
            del appids[:]
            del completeappids[:]
            del notfoundappids[:]
            del nofileappids[:]
        # elif not args.skipparsing:
        #     for filename in glob.glob(os.path.join(seriespath,'*.xml')):
        #         logging.info('-- Start Processing file: '+filename)
        #         fname = os.path.join(seriespath, filename)
        #         fn = changeExt(fname, 'json')
        #         if not os.path.isfile(fn):
        #             fileappid = (os.path.basename(filename)).split('_')[0]
        #             ifwnum = (os.path.basename(filename)).split('_')[1]
        #             #type set to oa for office actions
        #             doccontent['type'] = 'oa'
        #             doccontent['appid'] = fileappid
        #             #IFW number for action
        #             doccontent['ifwnumber'] = ifwnum
        #             if parseXML(fname):
        #                 if getPALMData(fileappid):
        #                     if getDocDate(fileappid, ifwnum):
        #                         if writeToJSON(fn):
        #                             numoffileswritten += 1
        #                             logging.info('-- {} - Complete processing for file: {}'.format(numoffileswritten,fn))
        #                             if not args.skipsolr:
        #                                 logging.info('-- Reading JSON file: '+fn)
        #                                 #readJSON(fn)
        #                         else:
        #                             logging.error('-- write to JSON for file: '+filename+' failed')
        #                     else:
        #                         logging.error('-- Retrieval of Doc Date for file: '+filename+' failed')
        #                 else:
        #                     logging.error('-- Extraction of PALM data for file: '+filename+' failed')
        #             else:
        #                 logging.error('-- Parsing of file: '+filename+' failed')
        #         else:
        #             logging.info('File: '+fn+' already exists')
        #         doccontent.clear()
        #     writeLogs(os.path.join(seriespath,'notfoundPALM.log'),notfoundPALM)
        #     writeLogs(os.path.join(seriespath,'notfoundCMS.log'),notfoundCMS)
        #     writeLogs(os.path.join(seriespath,'badfiles.log'),badfiles)
        #     del notfoundPALM[:]
        #     del notfoundCMS[:]
        #     del badfiles[:]
    logging.info("-- [JOB END] -------------------")