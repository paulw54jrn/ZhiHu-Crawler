#! /usr/bin/python
# -*- coding: utf-8 -*-
from lxml import etree
import requests, re, sys, Queue, threading, time, 

NB_WORKER_THREAD = 5
BASE_DOMAIN      = 'http://www.zhihu.com'
SILENT_OUTPUT    = False

def answerPageScanner( loginSession, userAnswerURL, answerPageQueue):
    response     = loginSession.get(userAnswerURL)
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
        raw_next_url = re.findall(u'<span class="zg-gray-normal">下一页</span>',raw_data)
        if not SILENT_OUTPUT:
            print "Answer Page "+str(page_count)+" Scanned..." 
        page_count += 1
        answerPageQueue.put(raw_data)
    
def questionLinkExtractor( answerPageQueue, questionLinkQueue):
    while True:
        raw_data = answerPageQueue.get()
        questionLinks = re.findall("<h2><a class=\"question_link\" href=\"(.*)\">.*</a></h2>",raw_data)

        for i in range(len( questionLinks)):
            questionLinkQueue.put( questionLinks[i] )
        
        if not SILENT_OUTPUT:
            print str(len(questionLinks)) + " link(s) Extracted..." 
        answerPageQueue.task_done()

def answerContentExtractor( loginSession, questionLinkQueue , answerContentList) :
    while True:
        global BASE_DOMAIN
        answerContentPageURL = questionLinkQueue.get()
        
        if not SILENT_OUTPUT:
            print "Sending Request To Retrieve " + answerContentPageURL 
            
        response       = loginSession.get( BASE_DOMAIN + answerContentPageURL )
        raw_data       = response.text
        questionID     = answerContentPageURL[answerContentPageURL.find('/question/')+10:answerContentPageURL.find('/answer/')]
        answerID       = answerContentPageURL[answerContentPageURL.find('/answer/')+8:]
        title          = re.findall('<title>(.*)</title>',raw_data)[0]
        
        try:
            questionInfo   = re.findall('<div class="zm-editable-content">(.*)</div>',raw_data)[0]
        except IndexError:
            questionInfo   = ""
        try:
            answerContent  = re.findall('<div class=" zm-editable-content clearfix">(.*)',raw_data)[0]
        except IndexError:
            questionLinkQueue.task_done()
            return
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
                  'voteCount'     : voteCount
                  'lastEdit'      : lastEdit
                }
        if not SILENT_OUTPUT:
            print 'Answer ('+str(answerID)+') Extracted...' 
        answerContentList.append(result)
        questionLinkQueue.task_done()



def getUserInfo( loginSession, userPageURL) :
    URL           = userPageURL + '/about'
    response      = loginSession.get(URL)
    raw_data      = response.text
    
    if not SILENT_OUTPUT : 
        print "Extracting User Info : " + URL
    
    try:
        name          = re.findall('<a class=\"name\" href=\".*?\">(.*)</a>',raw_data)[0]
    except IndexError :
        name          = ""
    try: 
        bio           = re.findall('<span class=\"bio\" title=\".*?\">(.*)</span>',raw_data)[0]
    except IndexError :
        bio           = ""
    try: 
        bussinessItem = re.findall('<span class=\"business item\" title=\".*?\">(.*)</span>',raw_data)[0]
    except IndexError :
        bussinessItem = ""
    try:
        description   = re.findall('<span class="content">(.*?)</span>',raw_data.replace('\n',''))[0]
    except IndexError :
        description   = ""
    
    result = {
                'name' : name,
                'bio'  : bio,
                'bussinessItem' : bussinessItem,
                'description'   : description
                }
    return result
        
def writeUserInfo( node, userInfo ) :
    for key in userInfo:
        textNode      = etree.SubElement(node,key)
        textNode.text = userInfo[key]


def writeUserAnswer( node, userAnswer) :
    for key in userAnswer:
        textNode      = etree.SubElement(node,key)
        textNode.text = userAnswer[key]
        
        
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
    
    
def extractUserAnswer( loginSession, userName, silent = False):
    global SILENT_OUTPUT
    SILENT_OUTPUT = silent
    s             = loginSession
    userURL       = 'http://www.zhihu.com/people/' + userName
    baseURL       = userURL + '/answers/'
    loginURL      = 'http://www.zhihu.com/login'

    if not SILENT_OUTPUT:
        print 'Login to Zhihu.com...' 
    
    answerPageQueue    = Queue.Queue()
    questionLinkQueue  = Queue.Queue()
    answerContentList  = []
    
    answerPageScannerThread = threading.Thread(target = answerPageScanner,args=(s,baseURL,answerPageQueue))
    answerPageScannerThread.daemon = True
    answerPageScannerThread.start()
    
    questionLinkExtractorThread = threading.Thread(target = questionLinkExtractor,args=(answerPageQueue,questionLinkQueue))
    questionLinkExtractorThread.daemon = True
    questionLinkExtractorThread.start()
    
    global NB_WORKER_THREAD
    for i in range(NB_WORKER_THREAD) :
        answerContentExtractorThread = threading.Thread(target = answerContentExtractor,args=(s,questionLinkQueue,answerContentList))
        answerContentExtractorThread.daemon = True
        answerContentExtractorThread.start()
    
    time.sleep(5)
    answerPageQueue.join()
    questionLinkQueue.join()
    userInfo = getUserInfo(s, userURL)
    result = { 
               'userInfo'   : userInfo,
               'userAnswer' : answerContentList
               }
    return result

def main():
    if len( sys.argv ) != 5:
        print "Usage : UserName, Password, UserToBeExtracted, XMLFileName" 
        print str(len( sys.argv)) + " argument(s) received." 
        sys.exit(1)
        
    s           = requests.session()
    login_data  = { 'email' : sys.argv[1] , 'password' : sys.argv[2] }
    userName    = sys.argv[3]
    XMLFileName = sys.argv[4]
    
    userURL     = 'http://www.zhihu.com/people/' + userName
    baseURL     = userURL + '/answers/'
    loginURL    = 'http://www.zhihu.com/login'
    
    if not SILENT_OUTPUT:
        print 'Login to Zhihu.com...' 
    s.post(loginURL,login_data)
    r = s.get(baseURL)
    
    if not SILENT_OUTPUT:
        print r 
    if r.status_code != 200 : 
        print "Page Access Error. Url = " + baseURL
        sys.exit(1)
    
    answerPageQueue    = Queue.Queue()
    questionLinkQueue  = Queue.Queue()
    answerContentList  = []
    
    answerPageScannerThread = threading.Thread(target = answerPageScanner,args=(s,baseURL,answerPageQueue))
    answerPageScannerThread.daemon = True
    answerPageScannerThread.start()
    
    questionLinkExtractorThread = threading.Thread(target = questionLinkExtractor,args=(answerPageQueue,questionLinkQueue))
    questionLinkExtractorThread.daemon = True
    questionLinkExtractorThread.start()
    
    global NB_WORKER_THREAD
    for i in range(NB_WORKER_THREAD) :
        answerContentExtractorThread = threading.Thread(target = answerContentExtractor,args=(s,questionLinkQueue,answerContentList))
        answerContentExtractorThread.daemon = True
        answerContentExtractorThread.start()
    
    time.sleep(5)
    answerPageQueue.join()
    questionLinkQueue.join()
    
    if not SILENT_OUTPUT:
        print "Writing to XML..." 
        
    writeToXML(XMLFileName,getUserInfo(s,userURL),answerContentList)
    
    if not SILENT_OUTPUT:
        print "Done..." 
    
    if not SILENT_OUTPUT:
        print "Total Answer(s) written : " + str(len(answerContentList)) 

if __name__ == '__main__':
    main()
#    if len( sys.argv ) != 5:
#        print "Usage : UserName, Password, UserToBeExtracted, XMLFileName" 
#        print str(len( sys.argv)) + " argument(s) received." 
#        sys.exit(1)
#        
#    s           = requests.session()
#    login_data  = { 'email' : sys.argv[1] , 'password' : sys.argv[2] }
#    s.post('http://www.zhihu.com/login',login_data)
#    userName    = sys.argv[3]
#    XMLFileName = sys.argv[4]
#    result = extractUserAnswer(s,userName)
#    writeToXML(XMLFileName,result['userInfo'],result['userAnswer'])


