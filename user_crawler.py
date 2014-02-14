#! /usr/bin/python
# -*- coding: utf-8 -*-

import requests, re, sys, json, Queue

SILENT_OUTPUT = False
NEXT_PAGE_URL = 'http://www.zhihu.com/node/ProfileFolloweesListV2'


def followeeScanner( loginSession, userProfilePageURL) :
    pass
    

def extractor( loginSession, userProfilePageURL):
    response = loginSession.get( userProfilePageURL )
    raw_data = response.text
    
    try : 
        selfURL = re.findall('<a href="(.*)" class="zu-top-nav-userinfo ">',raw_data)[0]
    except IndexError :
        selfURL = ""
        print >> sys.stderr, "HomePage Access Error. Abort..."
        sys.exit(1)
        
    followeePageURL  = userProfilePageURL + selfURL + '/followees'
    print "Accessing Page " + followeePageURL
    
    raw_data = loginSession.get( followeePageURL ).text 
    
    pageFolloweeList = []
    pageCount        = 1
    try:
        linkList = re.findall('<h2 class=\"zm-list-content-title\"><a data-tip=\".*\" href=\"(.*)\" class=\"zg-link\" title=\".*\">.*</a></h2>',raw_data)
        pageFolloweeList.extend(linkList)
        print "Extracting followee list page " + str(pageCount) + " with " + str(len(linkList)) + " entries..."
    except IndexError:
        linkList = []
        print >> sys.stderr, "Followee links for Page 1 Extract Failed..."
    
            
    requestHeader = {
                'Accept'          : '*/*',
                'Accept-Encoding' : 'gzip,deflate,sdch',
                'Accept-Language' : 'en-US,en;q=0.8',
                'Connection'      : 'keep-alive',
                'Content-Type'    : 'application/x-www-form-urlencoded; charset=UTF-8',
                'Host'            : 'www.zhihu.com',
                'Origin'          : 'http://www.zhihu.com',
                'Referer'         : followeePageURL,
                'User-Agent'      :'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/32.0.1700.107 Safari/537.36',
                }
    
    try:
        hashID = re.findall('\"user_hash\"\:\"(.*)\"}</script>',raw_data)[0]
        xsrf   = re.findall('<input type=\"hidden\" name=\"_xsrf\" value=\"(.*)\"/>',raw_data)[0]
    except IndexError:
        print >> sys.stderr, "HashId or xsrf Extraction Failed...Abort..."
        sys.exit(1)
    
    offset   = 20
    params   = json.dumps({ 'hash_id':hashID, 'order_by':'created', 'offset':offset })
    payload  = {'method':'next', 'params':params, '_xsrf':xsrf}
    
    global NEXT_PAGE_URL
    response   = loginSession.post( NEXT_PAGE_URL , data = payload , headers = requestHeader ) 
    response   =  json.loads(response.text)
    
    while len(response['msg']) > 0 :
        pageCount += 1
        offset    += 20
        print "Extracting followee list page " + str(pageCount) + " with " + str(len(response['msg'])) + " entries..."
        for count in range(len( response['msg'])) :
            link = re.findall('<h2 class=\"zm-list-content-title\"><a data-tip=\".*\" href=\"(.*)\" class=\"zg-link\" title=\".*\">.*</a></h2>',response['msg'][count])[0]
            pageFolloweeList.append(link)
        params     = json.dumps({ 'hash_id':hashID, 'order_by':'created', 'offset':offset })
        payload    = {'method':'next', 'params':params, '_xsrf':xsrf}
        response   = loginSession.post( NEXT_PAGE_URL , data = payload , headers = requestHeader ) 
        response   = json.loads(response.text)
        
    print str(len(pageFolloweeList)) + " links extracted..."
    
if __name__ == "__main__":
    if len( sys.argv ) != 3:
        print "Usage : Email, Password" 
        print str(len( sys.argv)) + " argument(s) received." 
        sys.exit(1)
        
    loginSession= requests.session()
    login_data  = { 'email' : sys.argv[1] , 'password' : sys.argv[2] }
    
    loginURL    = 'http://www.zhihu.com/login'
    userProfilePageURL = "http://www.zhihu.com"
    
    if not SILENT_OUTPUT:
        print 'Login to Zhihu.com...' 
    loginSession.post(loginURL,login_data)
    response = loginSession.get(userProfilePageURL)
        
    print response
    if response.status_code != 200:
        print 'Error accessing page...'
        sys.exit(1)

    extractor(loginSession, userProfilePageURL)
