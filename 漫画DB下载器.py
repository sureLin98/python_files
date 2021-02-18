import requests
import re
import os
import img2pdf
import shutil
import time
import pikepdf
from pikepdf import _cpphelpers
from bs4 import BeautifulSoup
from threading import Thread
from threading import current_thread
from requests.adapters import HTTPAdapter

baseurl='https://www.manhuadb.com'

def get_source(url):
    header={
        'user-agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36'
    }
    reqs = requests.Session()
    reqs.mount('http://', HTTPAdapter(max_retries=3))  # 如果出现异常则再尝试3次
    reqs.mount('https://', HTTPAdapter(max_retries=3))
    try:
        res = reqs.get(url=url, headers=header)
    except requests.exceptions.RequestException as e:
        print('! 无响应 '+str(e))
    bs = BeautifulSoup(str(res.text), 'lxml')
    return bs

def search_comics():
    global baseurl
    comics_lists=[]
    keyword=input("> 请输入漫画名：")
    url=baseurl+'/search?q='+keyword
    dat=get_source(url)
    dat=dat.select('div[class*="col-4 col-sm-2 col-xl-1 px-1"]>div')

    for comic in dat:
        matchOBJ=re.match(r'.*"d-block".*href="(.*)".*title="(.*)".*class.*href="/author/.*title="(.*)"',str(comic),re.S)
        if matchOBJ:
            index=dat.index(comic)                  #漫画索引
            comic_author=matchOBJ.group(3)          #漫画作者
            comic_title=matchOBJ.group(2)           #漫画标题
            comic_url=baseurl + matchOBJ.group(1)   #漫画链接
            comics_lists.append([comic_author,comic_title,comic_url])
            print('{}.\t{} 《{}》 {}'.format(index, comic_author, comic_title,comic_url ))

    select_comics=input("> 请选择要下载的漫画：")
    while select_comics=='':
        select_comics = input("> 请选择要下载的漫画：")

    if select_comics=='exit':
        exit()

    return comics_lists[int(select_comics)]

def download(path,img_urls,p_min,p_max):

    header={
        'sec-ch-ua': '"Chromium";v = "88", "Google Chrome";v = "88", ";Not A Brand";v = "99"',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36'
    }

    reqs=requests.Session()
    reqs.mount('http://', HTTPAdapter(max_retries=3))      #如果出现异常则再尝试3次
    reqs.mount('https://', HTTPAdapter(max_retries=3))

    for img in img_urls:
        p=list(range(p_min,p_max))              #页数
        try:
            imgdata = reqs.get(url=img, headers=header).content
        except requests.exceptions.RequestException as e:
            print('! 无响应 '+str(e))
        imgfile = path+'/'+str(p[img_urls.index(img)]) + '.jpg'
        file = open(imgfile, 'wb')
        print('# '+str(current_thread())+' 正在下载\t'+imgfile)
        file.write(imgdata)
        print('# '+str(current_thread())+' '+imgfile+'\t下载完成！')
        file.close()

    print('> '+str(current_thread())+'已结束！')

def get_img(chapter_name,link):
    global comic_name, \
        comic_author,\
        thread_list
    temp=[]
    chapter_name = chapter_name.replace('_', '-')
    link_sources = get_source(link)  # 获取章节的bs对象
    matchOBJ = re.match(r'.*共(.*)页.*', str(link_sources.select('li[class*="breadcrumb-item active"]')), re.S)  # 获取各章节页数
    if matchOBJ:
        pages=int(matchOBJ.group(1))
    else:
        print('! 无法获取页数！')
        exit()
    for p in range(1,pages+1):
        url=link.replace('.html','_p'+str(p)+'.html')
        temp.append(get_source(url).img['src'])

    print('> 已获取{}'.format(temp))

    print('> 共{}页'.format(pages))

    img_urls=temp
    div=int(pages/2)
    path='./{}《{}》/{}'.format(comic_author,comic_name,chapter_name)

    print('> 开始创建线程下载. . .')

    if not os.path.exists(path):            #创建漫画章节目录
        os.makedirs(path)

    thread1=Thread(target=download,args=(path,img_urls[:div],0,div))
    thread1.setName('{}_0_{}'.format(chapter_name,div))
    thread1.start()

    thread_list.append(thread1)

    thread2=Thread(target=download, args=(path, img_urls[div:],div,pages))
    thread2.setName('{}_{}_{}'.format(chapter_name,div,pages))
    thread2.start()

    thread_list.append(thread2)

    thread3=Thread(target=wait_convert_pdf,args=(thread1,thread2))
    thread3.start()
    thread3.setName('{}_PDF转换'.format(chapter_name))

    thread_list.append(thread3)

def process_comics(comic_data):
    global baseurl,\
        img_url_lists,\
        comic_name,\
        comic_author,\
        thread_list

    x=0
    index=[]
    chapter_lists=[]
    img_url_lists=[]

    comic_author=comic_data[0]
    comic_name=comic_data[1]
    url=comic_data[2]
    dat=get_source(url)
    comic_sources=list(dat.select('div[class*="tab-pane fade show"]>ol'))
    comic_sources_titles=[i.text for i in dat.select('a[class*="nav-link"]>span')]
    if len(comic_sources)>1:
        for i in comic_sources_titles:
            print('{}.\t{}'.format(comic_sources_titles.index(i),i))

        x=int(input("请选择要下载的版本："))
        while x>=len(comic_sources):
            print('输入非法，请重新输入!')
            x = int(input("> 请选择要下载的版本："))

    comic=comic_sources[x]

    print('> 正在获取漫画，请稍等（可能时间比较长，受漫画章数、页数而定）. . . ')

    chapters=BeautifulSoup(str(comic),'lxml').select('ol>li')

    for chapter in chapters:
        matchOBJ=re.match(r'.*href="(.*html)".*title="(.*)">.*',str(chapter),re.S)
        name=matchOBJ.group(2)                  #章节名字
        link=baseurl+matchOBJ.group(1)          #章节链接
        chapter_lists.append([name,link])
        print('{}.\t{} {}'.format(chapters.index(chapter)+1, name,link))

    print('> 说明：all---下载全部\t1,3,4,10---仅下载部分离散章节\t1:10或3:---下载部分连续章节')

    select_chapter=input('> 请选择要下载的章节:')
    while select_chapter=='':
        select_chapter = input('> 请选择要下载的章节:')

    n=len(chapter_lists)

    if select_chapter=='all' or select_chapter=='ALL':
        index=list(range(0,n))                                              #全部下载
    elif ':' in select_chapter:                                             #下载部分
        temp=select_chapter.split(':')
        if temp[1]!='':
            index=list(range(int(temp[0])-1,int(temp[1])))
        else:
            index=list(range(int(temp[0])-1,n))
    elif len(str(select_chapter).split(','))>=1:
        index=[int(i)-1 for i in str(select_chapter).split(',')]
    else:
        print('! 输入错误')
        exit()

    print('> 准备下载. . .')

    for i in index:
        name=chapter_lists[i][0]
        link=chapter_lists[i][1]
        thread=Thread(target=get_img,args=(name,link))
        thread.setName(name)
        thread.start()
        thread_list.append(thread)

def convert_pdf(chapter_name):
    global comic_name,\
        comic_author
    comic_path='.\\{}《{}》'.format(comic_author,comic_name)

    pdf_path = comic_path + '\\PDF\\'
    chapter_path=comic_path+'\\'+chapter_name
    imgs_list = []

    if not os.path.exists(pdf_path):
        os.mkdir(pdf_path)

    print('# '+str(current_thread())+' 正在转换'+chapter_name)

    imgs=os.listdir(chapter_path)

    imgs.sort(key=lambda x:int(x[:-4]))

    for i in imgs:
        imgs_path = os.path.join(chapter_path, i)
        imgs_list.append(imgs_path)

    with open(pdf_path + chapter_name + '.pdf', 'wb') as f:
        f.write(img2pdf.convert(imgs_list))

    print('> '+str(current_thread())+' '+chapter_name+'转换完成!')

def wait_convert_pdf(thread1,thread2):
    thread1.join()
    thread2.join()
    chapter_name=str(thread2.name).split('_')[0]
    convert_pdf(chapter_name)

def clear():
    global comic_name,\
        comic_author

    print('> 开始清理临时文件')

    comic_path='.\\{}《{}》'.format(comic_author,comic_name)
    dirs=os.listdir(comic_path)
    dirs.remove('PDF')

    for d in dirs:
        shutil.rmtree(os.path.join(comic_path,d))

    print('> 临时文件清理完成')

def main():
    global thread_list
    thread_list=[]
    comics=search_comics()
    process_comics(comics)
    for thread in thread_list:
        thread.join()
    clear()
    print('> 主线程退出!')
    time.sleep(3)

if __name__ == '__main__':
    main()