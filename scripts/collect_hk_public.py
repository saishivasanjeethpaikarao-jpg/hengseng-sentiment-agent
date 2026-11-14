#!/usr/bin/env python3
"""Bounded public HK social sample. No keys, login, Apify, proxy or paid service.

Moomoo: public stock page -> linked posts -> schema.org publication timestamps.
  The stock page is fetched with plain HTTP: its HTML embeds the post links,
  so no browser is needed (verified 2026-11-14; the earlier "browser required"
  note was wrong for the current page).
LIHKG: two public routes, both with the browser headers the endpoint
  requires (Referer + X-Requested-With):
  (a) direct search API (api_v2/thread/search), keyword per ticker, pages 1-5;
  (b) finance-category listing (api_v2/thread/category?cat_id=15), pages 1-5,
      titles filtered to the ticker's Chinese name / full code.
  Records are thread titles only (not reply text), finance category only.
This direct local collection is NOT an Apify run or exhaustive forum archive.

Why LIHKG used to return zero rows: the previous collector captured the
search XHR from inside a headless browser, where the endpoint answers the
bare request with HTTP 403 (Cloudflare "Attention Required"). The same
endpoint answers 200 when the request carries a search-page Referer and
X-Requested-With: XMLHttpRequest, as a browser does. Verified 2026-11-14.
A second cause of low retention: keyword search returns relevance-ordered
threads spanning months, so few fall inside the 10-day window; the
newest-first category listing is the route that finds recent threads.
"""
from __future__ import annotations
import json,re,time
from pathlib import Path
from datetime import datetime,timedelta,timezone
from urllib.parse import urlencode
import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw/hk_public';OUT=ROOT/'data/normalized'
ASSETS=[('0700.HK','00700','騰訊'),('9988.HK','09988','阿里'),('0005.HK','00005','匯豐'),('3690.HK','03690','美團'),('1299.HK','01299','友邦')]
# Category-listing title match: Chinese name or full 5-digit code. Bare short
# codes (700, 5) are deliberately not used -- they match unrelated numbers.
TITLE_KEYS={'0700.HK':('騰訊','00700'),'9988.HK':('阿里','09988','阿里巴巴'),
            '0005.HK':('匯豐','滙豐','00005','HSBC'),'3690.HK':('美團','03690'),
            '1299.HK':('友邦','01299','AIA')}
COLUMNS=['ticker','source','timestamp_utc','text','likes','reposts','views','author_followers','post_id','url','retrieved_at_utc','record_type','thread_title','timestamp_precision']
LIHKG_API='https://lihkg.com/api_v2/thread/search'
LIHKG_CATEGORY='https://lihkg.com/api_v2/thread/category'
LIHKG_HEADERS={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
               'Accept':'application/json','X-Requested-With':'XMLHttpRequest'}
LIHKG_SEARCH_PAGES=5
LIHKG_CATEGORY_PAGES=5

BROWSER_UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
# Moomoo serves the full server-rendered page (with post links) only when
# the request carries a real-browser User-Agent AND the client's default
# Accept headers. Adding browser-like Accept/Accept-Language headers
# flips the response to a 10KB JS shell with no links. Verified 2026-11-14:
# UA-only requests returned the 1.4MB page; UA + browser Accept headers
# returned the shell. So: User-Agent only, nothing else.

def numeric(text):
 try:return float(text.replace(',','').strip())
 except (ValueError,AttributeError):return None

def moomoo_post(url,ticker,now,start):
 r=requests.get(url,headers={'User-Agent':BROWSER_UA},timeout=30);r.raise_for_status()
 pid=url.split('?',1)[0].rstrip('/').rsplit('/',1)[-1].rsplit('-',1)[-1]
 (RAW/f'moomoo_post_{pid}.html').write_text(r.text,encoding='utf-8')
 s=BeautifulSoup(r.text,'html.parser');metadata=None
 for tag in s.select('script[type="application/ld+json"]'):
  try:
   candidate=json.loads(tag.string or tag.get_text())
   if isinstance(candidate,dict) and candidate.get('@type')=='DiscussionForumPosting':metadata=candidate;break
  except json.JSONDecodeError:pass
 if not metadata or not metadata.get('datePublished'):return None
 raw_stamp=str(metadata['datePublished'])
 # Moomoo's own data can carry hour 24 (e.g. 2026-11-06T24:55:38+08:00);
 # that is midnight of the next day, not a parse failure.
 m=re.match(r'^(\d{4}-\d{2}-\d{2})T24:(\d{2}:\d{2}(?:\.\d+)?)(.*)$',raw_stamp)
 if m:
  base=datetime.strptime(m.group(1),'%Y-%m-%d')+timedelta(days=1)
  raw_stamp=f"{base.date().isoformat()}T00:{m.group(2)}{m.group(3)}"
 try:stamp=pd.Timestamp(raw_stamp)
 except Exception:return None
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

def _lihkg_row(post,ticker,now):
 timestamp=datetime.fromtimestamp(post['create_time'],timezone.utc)
 return dict(ticker=ticker,source='LIHKG',timestamp_utc=timestamp.isoformat(),text=post['title'],
              likes=post.get('like_count'),reposts=None,views=None,author_followers=None,
              post_id=str(post['thread_id']),url=f"https://lihkg.com/thread/{post['thread_id']}/page/1",
              retrieved_at_utc=now.isoformat(),record_type='thread_title_only',
              thread_title=post['title'],timestamp_precision='source second')

def lihkg_collect(ticker,code,keyword,now,start):
 """Search API + finance-category listing. Returns (rows, status dict)."""
 rows=[];seen=set()
 status={'search_keyword':keyword,'search_pages':0,'search_results':0,'search_finance':0,
         'category_pages':0,'category_results':0,'category_matched':0,'retained':0,
         'http_status':None,'errors':[]}
 headers=dict(LIHKG_HEADERS)
 headers['Referer']='https://lihkg.com/search?'+urlencode({'q':keyword,'sort':'desc_create_time','type':'thread'})
 for page in range(1,LIHKG_SEARCH_PAGES+1):
  try:
   response=requests.get(LIHKG_API,params={'q':keyword,'sort':'desc_create_time','type':'thread','page':page},
                         headers=headers,timeout=30)
   status['search_pages']+=1;status['http_status']=response.status_code
   (RAW/f'lihkg_api_{code}_page{page}.json').write_bytes(response.content)
   if response.status_code!=200:
    status['errors'].append(f'search page {page}: HTTP {response.status_code}');break
   items=response.json().get('response',{}).get('items',[])
   status['search_results']+=len(items)
   if not items:break
   for post in items:
    if post.get('cat_id')!=15:continue
    status['search_finance']+=1
    stamp=datetime.fromtimestamp(post['create_time'],timezone.utc)
    if not start<=stamp<=now or str(post['thread_id']) in seen:continue
    seen.add(str(post['thread_id']));rows.append(_lihkg_row(post,ticker,now))
   time.sleep(.55)
  except Exception as e:
   status['errors'].append(f'search page {page}: {type(e).__name__}: {str(e)[:200]}');break
 cat_headers=dict(LIHKG_HEADERS);cat_headers['Referer']='https://lihkg.com/category/15'
 keys=TITLE_KEYS[ticker]
 for page in range(1,LIHKG_CATEGORY_PAGES+1):
  try:
   response=requests.get(LIHKG_CATEGORY,params={'cat_id':15,'page':page,'order':'now'},
                         headers=cat_headers,timeout=30)
   status['category_pages']+=1;status['http_status']=response.status_code
   (RAW/f'lihkg_category_page{page}.json').write_bytes(response.content)
   if response.status_code!=200:
    status['errors'].append(f'category page {page}: HTTP {response.status_code}');break
   items=response.json().get('response',{}).get('items',[])
   status['category_results']+=len(items)
   if not items:break
   for post in items:
    title=post.get('title') or ''
    if not any(k in title for k in keys):continue
    status['category_matched']+=1
    stamp=datetime.fromtimestamp(post['create_time'],timezone.utc)
    if not start<=stamp<=now or str(post['thread_id']) in seen:continue
    seen.add(str(post['thread_id']));rows.append(_lihkg_row(post,ticker,now))
   time.sleep(.55)
  except Exception as e:
   status['errors'].append(f'category page {page}: {type(e).__name__}: {str(e)[:200]}');break
 status['retained']=len(rows)
 return rows,status

def moomoo_stock_links(code):
 """Fetch the stock community page and return its linked post URLs.

 Moomoo's response varies per request: sometimes the full server-rendered
 page (with links), sometimes a 10KB JS shell (no links). Retry up to 5
 times with backoff until links are found.
 """
 url=f'https://www.moomoo.com/stock/{code}-HK/community'
 last=None
 for attempt in range(5):
  response=requests.get(url,headers={'User-Agent':BROWSER_UA},timeout=30);response.raise_for_status()
  last=response
  (RAW/f'moomoo_stock_{code}.html').write_text(response.text,encoding='utf-8')
  s=BeautifulSoup(response.text,'html.parser')
  links=list(dict.fromkeys(a['href'] for a in s.select('.nnq-list-item .publish-time a[href]') if '/community/feed/' in a['href']))
  if links:return response,links
  time.sleep(3.0)
 return last,[]

def main():
 RAW.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
 now=datetime.now(timezone.utc);start=now-timedelta(days=10);rows=[];status=[]
 for ticker,code,keyword in ASSETS:
  item={'ticker':ticker,'source':'Moomoo','status':'attempted','errors':[]}
  try:
   response,links=moomoo_stock_links(code)
   before=len(rows)
   for link in links[:20]:
    try:
     post=moomoo_post(link,ticker,now,start)
     if post and post['text']:rows.append(post)
    except Exception as e:item['errors'].append(f'{link}: {type(e).__name__}: {str(e)[:150]}')
    time.sleep(.25)
   item.update(http_status=response.status_code,linked_posts=len(links),retained=len(rows)-before,coverage='bounded public stock-page sample; not exhaustive; exact publication metadata')
  except Exception as e:item.update(status='failed',errors=[str(e)[:300]])
  status.append(item);print(json.dumps(item,ensure_ascii=False),flush=True)
 for ticker,code,keyword in ASSETS:
  item={'ticker':ticker,'source':'LIHKG','status':'attempted','errors':[]}
  try:
   found,detail=lihkg_collect(ticker,code,keyword,now,start)
   rows.extend(found)
   item.update(detail,coverage='direct public search API + finance-category listing; thread titles not full replies')
   item['errors']=detail['errors']
  except Exception as e:item.update(status='failed',errors=[str(e)[:300]])
  status.append(item);print(json.dumps(item,ensure_ascii=False),flush=True)
 df=pd.DataFrame(rows,columns=COLUMNS).drop_duplicates(['ticker','source','post_id'])
 df.to_csv(OUT/'hk_posts.csv',index=False)
 manifest={'retrieved_at_utc':now.isoformat(),'window_start_utc':start.isoformat(),'spend_usd':0,'method':'direct public local HTTP; LIHKG via public search API + category listing with browser headers; Moomoo via public page HTML; NOT Apify','exhaustive':False,'rows':len(df),'sources':status,'missing_fields':'null means unavailable, not zero'}
 (OUT/'hk_collection_status.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 print('SAVED',len(df),OUT/'hk_posts.csv',flush=True)
if __name__=='__main__':main()
