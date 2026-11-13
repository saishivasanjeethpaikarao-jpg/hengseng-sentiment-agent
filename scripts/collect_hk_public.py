#!/usr/bin/env python3
"""Bounded public HK social sample. No keys, login, Apify, proxy or paid service.

Moomoo: public stock page -> linked posts -> schema.org publication timestamps.
LIHKG: observed search endpoint, newest subjects, titles only (not reply text).
This direct local collection is NOT an Apify run or exhaustive forum archive.
"""
from __future__ import annotations
import json,re,time,os,shutil
from pathlib import Path
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
import pandas as pd
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/hk_public';OUT=ROOT/'data/normalized'
ASSETS=[('0700.HK','00700','騰訊'),('9988.HK','09988','阿里'),('0005.HK','00005','匯豐'),('3690.HK','03690','美團'),('1299.HK','01299','友邦')]
COLUMNS=['ticker','source','timestamp_utc','text','likes','reposts','views','author_followers','post_id','url','retrieved_at_utc','record_type','thread_title','timestamp_precision']

def numeric(text):
 try:return float(text.replace(',','').strip())
 except (ValueError,AttributeError):return None

def moomoo_post(url,ticker,now,start):
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=30);r.raise_for_status()
 pid=url.split('?',1)[0].rstrip('/').rsplit('/',1)[-1].rsplit('-',1)[-1]
 (RAW/f'moomoo_post_{pid}.html').write_text(r.text,encoding='utf-8')
 s=BeautifulSoup(r.text,'html.parser');metadata=None
 for tag in s.select('script[type="application/ld+json"]'):
  try:
   candidate=json.loads(tag.string or tag.get_text())
   if isinstance(candidate,dict) and candidate.get('@type')=='DiscussionForumPosting':metadata=candidate;break
  except json.JSONDecodeError:pass
 if not metadata or not metadata.get('datePublished'):return None
 stamp=pd.Timestamp(metadata['datePublished'])
 if stamp.tzinfo is None:raise ValueError('Unzoned source timestamp')
 stamp=stamp.tz_convert('UTC')
 if not start<=stamp.to_pydatetime()<=now:return None
 headline=metadata.get('headline','')
 bodies=[n.get_text(' ',strip=True) for n in s.select('.richtext-module-wrapper')]
 text='\n'.join(dict.fromkeys([headline]+bodies)).strip()
 likes=None
 for reaction in s.select('.face-like-bar__item'):
  image=reaction.find('img')
  if image and image.get('alt')=='Thumbs Up':likes=numeric(reaction.get_text(' ',strip=True))
 body=s.select_one('.feed-detail__content-wrapper')
 match=re.search(r'([\d,]+)\s+Views',body.get_text(' ',strip=True) if body else '')
 return dict(ticker=ticker,source='Moomoo',timestamp_utc=stamp.isoformat(),text=text,likes=likes,reposts=None,views=numeric(match.group(1)) if match else None,author_followers=None,post_id=pid,url=url,retrieved_at_utc=now.isoformat(),record_type='public_post',thread_title='',timestamp_precision='source second')

def main():
 RAW.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
 now=datetime.now(timezone.utc);start=now-timedelta(days=10);rows=[];status=[]
 with sync_playwright() as p:
  executable=os.getenv('CHROMIUM_EXECUTABLE') or shutil.which('chromium') or shutil.which('google-chrome')
  launch={'headless':True}
  if executable:launch['executable_path']=executable
  if os.name!='nt':launch['args']=['--no-sandbox']
  browser=p.chromium.launch(**launch)
  ctx=browser.new_context(timezone_id='Asia/Hong_Kong');page=ctx.new_page()
  for ticker,code,keyword in ASSETS:
   item={'ticker':ticker,'source':'Moomoo','status':'attempted','errors':[]}
   try:
    url=f'https://www.moomoo.com/stock/{code}-HK/community'
    response=page.goto(url,wait_until='domcontentloaded',timeout=40000);page.wait_for_timeout(1800)
    html=page.content();(RAW/f'moomoo_stock_{code}.html').write_text(html,encoding='utf-8')
    s=BeautifulSoup(html,'html.parser')
    links=list(dict.fromkeys(a['href'] for a in s.select('.nnq-list-item .publish-time a[href]') if '/community/feed/' in a['href']))[:20]
    before=len(rows)
    for link in links:
     try:
      post=moomoo_post(link,ticker,now,start)
      if post and post['text']:rows.append(post)
     except Exception as e:item['errors'].append(f'{link}: {type(e).__name__}: {str(e)[:150]}')
     time.sleep(.25)
    item.update(http_status=response.status if response else None,linked_posts=len(links),retained=len(rows)-before,coverage='bounded public stock-page sample; not exhaustive; exact publication metadata')
   except Exception as e:item.update(status='failed',errors=[str(e)[:300]])
   status.append(item);print(json.dumps(item,ensure_ascii=False),flush=True)
  for ticker,code,keyword in ASSETS:
   item={'ticker':ticker,'source':'LIHKG','status':'attempted','errors':[]};captured=[]
   def receive(response):
    if '/api_v2/thread/search?' in response.url:
     try:captured.append(response.json())
     except Exception:pass
   page.on('response',receive)
   try:
    query=urlencode({'q':keyword,'sort':'desc_create_time','type':'thread'})
    url='https://lihkg.com/search?'+query
    page.goto(url,wait_until='domcontentloaded',timeout=35000);page.wait_for_timeout(1800)
    (RAW/f'lihkg_search_{code}.html').write_text(page.content(),encoding='utf-8')
    (RAW/f'lihkg_search_{code}.json').write_text(json.dumps(captured,ensure_ascii=False),encoding='utf-8')
    candidates=[x for payload in captured for x in payload.get('response',{}).get('items',[])]
    before=len(rows)
    for post in candidates:
     timestamp=datetime.fromtimestamp(post['create_time'],timezone.utc)
     if not start<=timestamp<=now or post.get('cat_id')!=15:continue
     rows.append(dict(ticker=ticker,source='LIHKG',timestamp_utc=timestamp.isoformat(),text=post['title'],likes=post.get('like_count'),reposts=None,views=None,author_followers=None,post_id=str(post['thread_id']),url=f"https://lihkg.com/thread/{post['thread_id']}/page/1",retrieved_at_utc=now.isoformat(),record_type='thread_title_only',thread_title=post['title'],timestamp_precision='source second'))
    item.update(search_keyword=keyword,search_results=len(candidates),retained=len(rows)-before,coverage='newest first page only; finance category; thread titles not full replies')
   except Exception as e:item.update(status='failed',errors=[str(e)[:300]])
   page.remove_listener('response',receive);status.append(item);print(json.dumps(item,ensure_ascii=False),flush=True)
  browser.close()
 df=pd.DataFrame(rows,columns=COLUMNS).drop_duplicates(['ticker','source','post_id'])
 df.to_csv(OUT/'hk_posts.csv',index=False)
 manifest={'retrieved_at_utc':now.isoformat(),'window_start_utc':start.isoformat(),'spend_usd':0,'method':'direct public local HTTP/browser; NOT Apify','exhaustive':False,'rows':len(df),'sources':status,'missing_fields':'null means unavailable, not zero'}
 (OUT/'hk_collection_status.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 print('SAVED',len(df),OUT/'hk_posts.csv',flush=True)
if __name__=='__main__':main()
