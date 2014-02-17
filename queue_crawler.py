#! /usr/bin/python
# -*- coding: utf-8 -*-
from lxml import etree
from bs4  import BeautifulSoup

import requests, re, sys, Queue, threading, time, os, random

NB_WORKER_THREAD = 3         #number of worker threads. 
BASE_DOMAIN      = 'http://www.zhihu.com' 
SILENT_OUTPUT    = False     #Do not output diagnostic information 
BASE_FOLDER      = 'Answer/' #folder to contain all the files
MAX_CONN_RETRY   = 3         #max number of re-connection before abort
CONN_TIMEOUT     = 10        #max timeout before abort

#Scan the web page, extract the URL of next page and put it
#to the answerPageQueue
def answerPageScanner( loginSession, userAnswerURL, answerPageQueue):
    response     = loginSession.get(userAnswerURL, timeout = CONN_TIMEOUT)
    raw_data     = response.text
    raw_next_url = re.findall(u'<span class="zg-gray-normal">下一页</span>',raw_data)
    page_count   = 2

    answerPageQueue.put(raw_data)
    if not SILENT_OUTPUT:
        print "Answer Page 1 Scanned..." 
    
    while len(raw_next_url) == 0 :
        URL = userAnswerURL + "?page=" + str(page_count)
        response = loginSession.get(URL)
        raw_data = response.text
        raw_next_url  = re.findall(u'<span class="zg-gray-normal">下一页</span>',raw_data)
        questionLinks = re.findall("<h2><a class=\"question_link\" href=\"(.*)\">.*</a></h2>",raw_data)
        if len(questionLinks) == 0:
            break
            
        if not SILENT_OUTPUT:
            print "Answer Page "+str(page_count)+" Scanned..." 
        page_count += 1
        answerPageQueue.put(raw_data)

#Scan the page, extract all the question links , then 
#put the URLs in the questionLinkQueue
def questionLinkExtractor( answerPageQueue, questionLinkQueue):
    while True:
        raw_data = answerPageQueue.get()
        questionLinks = re.findall("<h2><a class=\"question_link\" href=\"(.*)\">.*</a></h2>",raw_data)

        for i in range(len( questionLinks)):
            questionLinkQueue.put( {'URL':questionLinks[i],'timeoutNb':0} )
        
        if not SILENT_OUTPUT:
            print str(len(questionLinks)) + " link(s) Extracted..." 
        answerPageQueue.task_done()
        
#Scan through the extracted html document , extract all the img 
#tags, then change the image's src to the local file
def imgLinkExtractorModifier( answerResult, imageProcessQueue):
    try:
        answerID= answerResult['answerID']
        html    = BeautifulSoup(answerResult['answerContent'])
        img     = html.find_all(re.compile('img'))
        imgList = []
        
        for lnk in img:
            if lnk.get('data-actualsrc') != None:
                imageProcessQueue.put( {'answerID':answerID,'imageLink':lnk['data-actualsrc'],'nbTimeout':0})
                linkPath = str(lnk['data-actualsrc']).split('/')
                fileName = linkPath[len(linkPath)-1]
                imgList.append(fileName)
                lnk['src'] = answerID + "/" + fileName
            else:
                lnk.decompose()
                
        answerResult['answerContent'] = str(html).decode('utf-8')
        answerResult['img'] = imgList
        return answerResult
    
    except :
        return
    
#Scan the answer page, extract the title, id, description of the question, alone
#with the answer content, put them into a dictionary, then push the dictionary
#into the answerContentList. All the image links that were extracted from the 
#answer content will be put into the imageProcessQueue
def answerContentExtractor( loginSession, questionLinkQueue , answerContentList, imageProcessQueue) :
    while True:
        global BASE_DOMAIN
         
        answerContentHash    = questionLinkQueue.get()
        answerContentPageURL = answerContentHash['URL']
        timeoutNb            = answerContentHash['timeoutNb']
        
        if int(timeoutNb) > MAX_CONN_RETRY : 
            print >> sys.stderr , "Max retry reached. Abort : " + answerContentPageURL
            questionLinkQueue.task_done()
            continue 
        
        if not SILENT_OUTPUT:
            print "Sending Request To Retrieve " + answerContentPageURL 
        
        try :     
            response       = loginSession.get(BASE_DOMAIN + answerContentPageURL , timeout = CONN_TIMEOUT )
            raw_data       = response.text
            questionID     = answerContentPageURL[answerContentPageURL.find('/question/')+10:answerContentPageURL.find('/answer/')]
            answerID       = answerContentPageURL[answerContentPageURL.find('/answer/')+8:]
            title          = re.findall('<title>(.*)</title>',raw_data)[0]
        except requests.exceptions.Timeout , IndexError:
            timeoutNb += 1
            putback = {'URL':answerContentPageURL,'timeoutNb':timeoutNb}
            questionLinkQueue.put( putback )
            questionLinkQueue.task_done()
            continue
            
        try:
            questionInfo   = re.findall('<div class="zm-editable-content">(.*)</div>',raw_data)[0]
        except IndexError:
            questionInfo   = ""
            
        try:
            answerContent  = re.findall('<div class=" zm-editable-content clearfix">(.*)',raw_data)[0]
        except IndexError:
            questionLinkQueue.task_done()
            continue
            
        try:
            voteCount  = re.findall('<a name="expand" class="zm-item-vote-count" href="javascript:;" data-votecount=".*?">(.*)</a>',raw_data)[0]
        except IndexError:
            voteCount = ""
        try:
            lastEdit = re.findall('<span class="time">(.*)</span>',raw_data)[0]
        except IndexError:
            lastEdit = ""
        
        result = {
                  'questionID'    : questionID,
                  'answerID'      : answerID,
                  'title'         : title,
                  'questionInfo'  : questionInfo,
                  'answerContent' : answerContent,
                  'voteCount'     : voteCount,
                  'lastEdit'      : lastEdit
                }
                
        result = imgLinkExtractorModifier(result, imageProcessQueue)
        
        if not SILENT_OUTPUT:
            print 'Answer ('+str(answerID)+') Extracted...' 
        answerContentList.append(result)
        questionLinkQueue.task_done()


#Access the user's profile page and extract user information.
def getUserInfo( loginSession, userPageURL) :
    URL           = userPageURL + '/about'
    response      = loginSession.get(URL)
    raw_data      = response.text
    
    strID         = userPageURL[userPageURL.find('/people/')+8:]
    
    if not SILENT_OUTPUT : 
        print "Extracting User Info : " + URL
    
    try:
        name = re.findall('<a class=\"name\" href=\".*?\">(.*)</a>',raw_data)[0]
    except IndexError :
        name = ""
    try: 
        bio  = re.findall('<span class=\"bio\" title=\".*?\">(.*)</span>',raw_data)[0]
    except IndexError :
        bio  = ""
    try: 
        bussinessItem \
        = re.findall('<span class=\"business item\" title=\".*?\">(.*)</span>',raw_data)[0]
    except IndexError :
        bussinessItem = ""
    try:
        description   \
        = re.findall('<span class="content">(.*?)</span>',raw_data.replace('\n',''))[0]
    except IndexError :
        description   = ""
    
    try:
        imageURL = re.findall('<img alt=\".*\"src=\"(.*)\"class=\"zm-profile-header-img zg-avatar-big zm-avatar-editor-preview\"/>',raw_data.replace('\n',''))[0]
    except IndexError :
        imageURL = ""
    print imageURL
    try:
        if len(imageURL) > 0 :
            fileName = imageURL.split('/')
            fileName = fileName[len(fileName)-1]
            filePath = BASE_FOLDER+strID+"/image/"
            if not os.path.exists( filePath ) :
                os.makedirs( filePath )
            
            r = loginSession.get( imageURL , stream=True, timeout=CONN_TIMEOUT)
            if r.status_code == 200 :
                with open( filePath + fileName,'wb+')as f:
                    for chunk in r.iter_content(): 
                        f.write(chunk)
        print "User Avatar Image Download Completed..."
    except requests.exceptions.Timeout:
        print "User Avatar Image Download Timeout..."
    
    result = {
                'strID': strID,
                'name' : name,
                'bio'  : bio,
                'bussinessItem' : bussinessItem,
                'description'   : description,
                'userAvatarImg' : fileName
                }
    return result
        
def writeUserInfo( node, userInfo ) :
    for key in userInfo:
        textNode      = etree.SubElement(node,key)
        textNode.text = etree.CDATA(userInfo[key])


def writeUserAnswer( node, userAnswer) :
    for key in userAnswer:
        if isinstance( userAnswer[key] , list) :
            for i in range(len(userAnswer[key])) :
                textNode      = etree.SubElement(node,key)
                textNode.text = etree.CDATA(userAnswer[key][i])
        else:
            textNode      = etree.SubElement(node,key)
            textNode.text = etree.CDATA(userAnswer[key])
        
        
def writeUserAnswerList( node, userAnswerList ) :
    for i in range(len(userAnswerList)):
        new_answer_node = etree.SubElement(node,"answer")
        writeUserAnswer( new_answer_node,  userAnswerList[i] )


def writeToXML( XMLPath, userInfo, completeAnswerList):
    root            = etree.Element('document')
    node_userInfo   = etree.SubElement(root,"userInfo")
    node_userAnswer = etree.SubElement(root,"userAnswers")
    
    writeUserInfo      ( node_userInfo   , userInfo )
    writeUserAnswerList( node_userAnswer , completeAnswerList )
    
    with open(XMLPath,'w') as f:
        f.write( etree.tostring(root, encoding = 'UTF-8' ,pretty_print = True ))


def writeFile( result ):
    userInfo   = result['userInfo']
    userAnswer = result['userAnswer']
    userName   = userInfo['strID']

    global BASE_FOLDER    
    if not os.path.exists(BASE_FOLDER+userName) :
        os.makedirs(BASE_FOLDER+userName)
 
    writeToXML(BASE_FOLDER+userName+"/"+userName+".xml", userInfo, userAnswer)

def imageDownloader( loginSession,userName, imageProcessQueue ):
    while True:
        imgSet    = imageProcessQueue.get()
        answerID  = imgSet['answerID']
        imageLink = imgSet['imageLink']
        nbTimeout = imgSet['nbTimeout']
        
        if not SILENT_OUTPUT :
            print "Starting to download file "+ imageLink
        
        global MAX_CONN_RETRY
        if nbTimeout > MAX_CONN_RETRY : 
            print >> sys.stderr ,"Max retry reached... aborting..." 
            imageProcessQueue.task_done()
            return
        
        imgPath   = BASE_FOLDER+userName+"/"+answerID+"/image/"
        fileName = str(imageLink).split('/')
        fileName  = fileName[len(fileName)-1]
        try:
            if not os.path.exists( imgPath ):
                waitTime = random.randint(0,10)
                time.sleep(waitTime)
                if not os.path.exists( imgPath ):
                    os.makedirs( imgPath )
        except :
            pass
            
        global CONN_TIMEOUT
        try:
            r = loginSession.get( imageLink , stream=True, timeout=CONN_TIMEOUT)
            if r.status_code == 200 :
                with open( imgPath + fileName,'wb+')as f:
                    for chunk in r.iter_content(): 
                        f.write(chunk)
            else:
                print >> sys.stderr , "Image " + fileName + " download Error..." 
            
            if not SILENT_OUTPUT:
                print "Image "+ fileName + " Download Completed..."
        except requests.exceptions.Timeout, request.exceptions.ConnectionError:
            print "Request for "+fileName+" timed out... Retrying..."
            imgSet['nbTimeout'] += 1
            imageProcessQueue.put(imgSet)
            
        imageProcessQueue.task_done()

def extractUserAnswer( loginSession, userName, silent = False):
    global SILENT_OUTPUT
    SILENT_OUTPUT = silent
    userURL       = 'http://www.zhihu.com/people/' + userName
    baseURL       = userURL + '/answers/'
    loginURL      = 'http://www.zhihu.com/login'

    answerPageQueue    = Queue.Queue()
    questionLinkQueue  = Queue.Queue()
    imageProcessQueue  = Queue.Queue()
    answerContentList  = []
    
    answerPageScannerThread = threading.Thread(target = answerPageScanner,args=(loginSession,baseURL,answerPageQueue))
    answerPageScannerThread.daemon = True
    answerPageScannerThread.start()
    
    questionLinkExtractorThread = threading.Thread(target = questionLinkExtractor,args=(answerPageQueue,questionLinkQueue))
    questionLinkExtractorThread.daemon = True
    questionLinkExtractorThread.start()
    
    global NB_WORKER_THREAD
    for i in range(NB_WORKER_THREAD) :
        answerContentExtractorThread = threading.Thread(target = answerContentExtractor,args=(loginSession,questionLinkQueue,answerContentList,imageProcessQueue))
        answerContentExtractorThread.daemon = True
        answerContentExtractorThread.start()    
            
        imageDownloaderThread = threading.Thread(target = imageDownloader,args=(loginSession,userName,imageProcessQueue))
        imageDownloaderThread.daemon = True
        imageDownloaderThread.start()
    
    
    time.sleep(5)
    answerPageQueue.join()
    questionLinkQueue.join()
    imageProcessQueue.join()
    
    userInfo = getUserInfo( loginSession, userURL)
    result = { 
               'userInfo'   : userInfo,
               'userAnswer' : answerContentList
               }
    return result

def main():
    if len( sys.argv ) != 4:
        print "Usage : Email, Password, UserToBeExtracted" 
        print str(len( sys.argv)) + " argument(s) received." 
        sys.exit(1)
        
    loginSession= requests.session()
    login_data  = { 'email' : sys.argv[1] , 'password' : sys.argv[2] }
    userName    = sys.argv[3]
    
    userURL     = 'http://www.zhihu.com/people/' + userName
    baseURL     = userURL + '/answers/'
    loginURL    = 'http://www.zhihu.com/login'
    
    if not SILENT_OUTPUT:
        print 'Login to Zhihu.com...' 
    loginSession.post(loginURL,login_data)
    response = loginSession.get(userURL+'/about')
        
    print response
    if response.status_code != 200:
        print 'Error accessing page...'
        sys.exit(1)
    
    result = extractUserAnswer(loginSession,userName)
    
    if not SILENT_OUTPUT:
        print "Writing to XML..." 
    writeFile(result)
    
    if not SILENT_OUTPUT:
        print "Done..." 
    
    if not SILENT_OUTPUT:
        print "Total Answer(s) written : " + str(len(result['userAnswer'])) 

if __name__ == '__main__':
    main()


