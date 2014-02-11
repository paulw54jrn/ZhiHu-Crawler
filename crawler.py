# -*- coding: utf-8 -*-
from lxml import etree
import requests, re, sys

def getAnwserPageURLs( loginSession, baseURL ) :
    response     = loginSession.get(baseURL)
    raw_data     = response.text
    raw_next_url = re.findall(u'<span class="zg-gray-normal">下一页</span>',raw_data)
    page_count   = 2
    
    answer       = []
    answer.append(baseURL)

    while len(raw_next_url) == 0 : 
       URL             = baseURL + "?page=" + str(page_count)
       response        = loginSession.get(URL)
       raw_data        = response.text
       raw_next_url    = re.findall(u'<span class="zg-gray-normal">下一页</span>',raw_data)
       page_count      += 1
       answer.append(URL)
    return answer

def getQuestionLinkURLs( loginSession, answerPageURL ) :
    response      = loginSession.get(answerPageURL)
    raw_data      = response.text
    questionLinks = re.findall("<h2><a class=\"question_link\" href=\"(.*)\">.*</a></h2>",raw_data)
    return questionLinks    
    
def getAnswerContent( loginSession, answerContentPageURL ) :
    response   = loginSession.get('http://www.zhihu.com'+answerContentPageURL)
    raw_data   = response.text
    
    questionID    = answerContentPageURL[answerContentPageURL.find('/question/')+10:answerContentPageURL.find('/answer/')]
    answerID      = answerContentPageURL[answerContentPageURL.find('/answer/')+8:]
    title         = re.findall('<title>(.*)</title>',raw_data)[0]
    questionInfo  = re.findall('<div class="zm-editable-content">(.*)</div>',raw_data)[0]
    answerContent = re.findall('<div class=" zm-editable-content clearfix">(.*)',raw_data)[0]
    
    result = {
              'questionID'    : questionID,
              'answerID'      : answerID,
              'title'         : title,
              'questionInfo'  : questionInfo,
              'answerContent' : answerContent
            }
    return result

def getUserInfo( loginSession, userPageURL) :
    response      = loginSession.get(userPageURL+'/about')
    raw_data      = response.text
    
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
    name               = etree.SubElement(node,'name')
    bio                = etree.SubElement(node,'bio')
    bussinessItem      = etree.SubElement(node,'bussinessItem')
    description        = etree.SubElement(node,'description')
    name.text          = etree.CDATA(userInfo['name'])
    bio.text           = etree.CDATA(userInfo['bio'])
    bussinessItem.text = etree.CDATA(userInfo['bussinessItem'])
    description.text   = etree.CDATA(userInfo['description'])


def writeUserAnswer( node, userAnswer) :
    questionId         = etree.SubElement(node,'questionID')
    questionId.text    = etree.CDATA(userAnswer['questionID'])
    answerId           = etree.SubElement(node,'answerID')
    answerId.text      = etree.CDATA(userAnswer['answerID'])
    title              = etree.SubElement(node,'title')
    title.text         = etree.CDATA(userAnswer['title'])
    questionInfo       = etree.SubElement(node,'questionInfo')
    questionInfo.text  = etree.CDATA(userAnswer['questionInfo'])
    answerContent      = etree.SubElement(node,'answerContent')
    answerContent.text = etree.CDATA(userAnswer['answerContent'])
    
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
    
def main() :
    if len( sys.argv ) != 5:
        print "Usage : UserName, Password, UserToBeRetrieved, XMLFileName."
        print str(len(sys.argv)) + " argument(s) received." 
        sys.exit(1)    
    
    s           = requests.session()
    login_data  = { 'email' : sys.argv[1] , 'password' : sys.argv[2] }
    userName    = sys.argv[3]
    XMLFileName = sys.argv[4]
    
    userURL    = 'http://www.zhihu.com/people/' + userName
    baseURL    = userURL + '/answers/'
    loginURL   = 'http://www.zhihu.com/login'
     
    print "Trying to Login Zhihu.com..."
    
    s.post(loginURL, login_data)
    r = s.get(baseURL)
    
    print r
    answerURLList = getAnwserPageURLs(s,baseURL)
    print "Answer Page Extracted..."
    
    questionLinks = []
    for i in range(len(answerURLList)) :
        questionLinks.extend( getQuestionLinkURLs(s,answerURLList[i]))
    print "Question Links Extracted..."
    
    answerList = []
    for i in range(len(questionLinks)):
        answerList.append( getAnswerContent(s,questionLinks[i]))
    print "All Answer Extracted..."
    
    print "Writing to XML..."
    writeToXML(XMLFileName,getUserInfo(s,userURL),answerList)

    print "Done..."
    
main()
