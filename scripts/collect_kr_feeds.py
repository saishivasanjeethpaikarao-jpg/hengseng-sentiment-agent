#!/usr/bin/env python3
"""Collect public Naver discussion posts using the endpoint observed in kr_probe.
This stage collects Naver. Run collect_daum_public.py afterward to append Daum and update combined status.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,time
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.parse import urlencode
import requests
from bs4 import BeautifulSoup

ASSETS={"005930.KS":("005930","Samsung Electronics"),"000660.KS":("000660","SK hynix"),"035420.KS":("035420","Naver Corporation"),"035720.KS":("035720","Kakao Corporation"),"005380.KS":("005380","Hyundai Motor")}
COLUMNS=["ticker","source","timestamp_utc","text","likes","reposts","views","author_followers","post_id","url"]
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; internship-public-collector/1.0)","Accept":"application/json, text/plain, */*","Accept-Language":"ko-KR,ko;q=0.9,en;q=0.5"}
NAVER='https://m.stock.naver.com/front-api/discussion/list'
NAVER_PAGE='https://m.stock.naver.com/domestic/stock/{}/discussion'
DAUM_PAGE='https://m.finance.daum.net/quotes/A{}/talks'

def iso(d): return d.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
def parse_dt(v):
 if not v:return None
 if isinstance(v,(int,float)):
  try:return datetime.fromtimestamp(v/1000 if v>10**11 else v,timezone.utc)
  except:return None
 try:
  d=datetime.fromisoformat(str(v).replace('Z','+00:00')); return ((d.replace(tzinfo=ZoneInfo('Asia/Seoul')).astimezone(timezone.utc)) if d.tzinfo is None else d.astimezone(timezone.utc))
 except:return None
def clean(v):
 if v is None:return None
 return re.sub(r'\s+',' ',BeautifulSoup(str(v),'html.parser').get_text(' ',strip=True)).strip() or None
def first(d,keys):
 for k in keys:
  if d.get(k) not in (None,''):return d[k]
 return None
def save_raw(raw, label, req, resp, root):
 p=raw/(label+'.json'); p.write_text(resp.text,encoding='utf-8')
 (raw/(label+'.meta.json')).write_text(json.dumps({'requested_url':req,'final_url':resp.url,'status_code':resp.status_code,'retrieved_at_utc':iso(datetime.now(timezone.utc)),'sha256':hashlib.sha256(resp.content).hexdigest()},ensure_ascii=False,indent=2),encoding='utf-8')
 return str(p.relative_to(root))
def naver_post(p,ticker,code,cutoff,now):
 dt=parse_dt(p.get('writtenAt'))
 if not dt or not(cutoff<=dt<=now):return None
 # isNews is deliberately retained as a separate classification, not silently mixed.
 if p.get('isNews') is True or p.get('postType') in ('news','itemNews'): return None
 text='\n'.join(x for x in [clean(p.get('title')),clean(first(p,('contentSwReplacedButImg','contentSwReplaced','content')))] if x)
 pid=str(p.get('id')) if p.get('id') is not None else None
 if not text or not pid:return None
 return {'ticker':ticker,'source':'naver_finance','timestamp_utc':iso(dt),'text':text,'likes':first(p,('recommendCount','reactionGoodCount')),'reposts':None,'views':first(p,('viewCount','views')),'author_followers':first(p.get('writer') or {},('followerCount','followers')),'post_id':pid,'url':f'https://m.stock.naver.com/domestic/stock/{code}/discussion/{pid}'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--days',type=int,default=10);ap.add_argument('--out',default='.');args=ap.parse_args();root=Path(args.out);raw=root/'data/raw/kr_public';norm=root/'data/normalized';raw.mkdir(parents=True,exist_ok=True);norm.mkdir(parents=True,exist_ok=True)
 now=datetime.now(timezone.utc);cutoff=now-timedelta(days=args.days);s=requests.Session();s.headers.update(HEADERS);rows=[];status={'collection_started_at_utc':iso(now),'collection_finished_at_utc':None,'now_utc':iso(now),'cutoff_utc':iso(cutoff),'window_days':args.days,'method':'requests HTTP only; observed public Naver JSON endpoint; no browser, login, proxy, Apify, Exa, paid API, or secret','sources':{},'news_items_excluded':[]}
 for ticker,(code,name) in ASSETS.items():
  key=f'naver_finance:{ticker}'; rec={'ticker':ticker,'asset_name':name,'source':'naver_finance','requested_url':NAVER+'?'+urlencode({'discussionType':'domesticStock','itemCode':code,'pageSize':50,'isHolderOnly':'false','excludesItemNews':'false','isItemNewsOnly':'false'}),'pages_requested':0,'records_seen':0,'records_in_window':0,'usable_timestamp_count':0,'min_timestamp_utc':None,'max_timestamp_utc':None,'raw_paths':[],'access_failure':None,'parser_note':'Observed cursor pagination: first request has no offset; subsequent requests pass prior result.lastOffset as offset. Max 5 pages.'}
  offset=None;seen=set()
  for page in range(1,6):
   q={'discussionType':'domesticStock','itemCode':code,'pageSize':50,'isHolderOnly':'false','excludesItemNews':'false','isItemNewsOnly':'false'}
   if offset is not None:q['offset']=offset
   req=NAVER+'?'+urlencode(q); label=f'naver_{code}_page{page}';
   try:r=s.get(req,timeout=25);rec['pages_requested']+=1;rec['raw_paths'].append(save_raw(raw,label,req,r,root))
   except Exception as e:rec['access_failure']=repr(e);break
   if r.status_code!=200:rec['access_failure']=f'HTTP {r.status_code}';break
   try:res=r.json().get('result') or {};posts=res.get('posts') or []
   except Exception as e:rec['access_failure']='invalid JSON '+repr(e);break
   rec['records_seen']+=len(posts); new=0
   for p in posts:
    pid=str(p.get('id')) if p.get('id') is not None else None
    if pid in seen:continue
    seen.add(pid);new+=1
    if p.get('isNews') is True or p.get('postType') in ('news','itemNews'):status['news_items_excluded'].append({'ticker':ticker,'source':'naver_finance','post_id':pid});continue
    row=naver_post(p,ticker,code,cutoff,now)
    if row:rows.append(row)
   nxt=res.get('lastOffset');
   if not posts or not nxt or str(nxt)==str(offset) or new==0:break
   offset=nxt;time.sleep(.55)
  ds=[r['timestamp_utc'] for r in rows if r['ticker']==ticker];rec['records_in_window']=len(ds);rec['usable_timestamp_count']=len(ds);rec['min_timestamp_utc']=min(ds) if ds else None;rec['max_timestamp_utc']=max(ds) if ds else None;status['sources'][key]=rec
  time.sleep(.55)
 # Daum is an explicit second collection stage; do not fabricate rows in the Naver collector.
 for ticker,(code,name) in ASSETS.items():status['sources'][f'daum_finance:{ticker}']={'ticker':ticker,'asset_name':name,'source':'daum_finance','requested_url':DAUM_PAGE.format(code),'records_seen':0,'records_in_window':0,'usable_timestamp_count':0,'access_failure':'Separate stage not run by this Naver script; run scripts/collect_daum_public.py afterward to collect Daum and update this placeholder.','parser_note':'Daum response 10 is social talks data (posts/title/content/createdAt/readCount/agreeCount/disagreeCount), while separate news/disclosure responses were excluded; no fabricated rows.'}
 ded={};
 for r in rows:ded[(r['source'],r['ticker'],r['post_id'])]=r
 cleanrows=list(ded.values());
 with (norm/'kr_posts.csv').open('w',newline='',encoding='utf-8-sig') as f:csv.DictWriter(f,fieldnames=COLUMNS).writeheader();csv.DictWriter(f,fieldnames=COLUMNS).writerows(cleanrows)
 status['collection_finished_at_utc']=iso(datetime.now(timezone.utc));status['total_records']=len(cleanrows);status['count_by_ticker_source']={k:sum(1 for r in cleanrows if f"{r['source']}:{r['ticker']}"==k) for k in status['sources']}
 (norm/'kr_collection_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
 prov={'retrieved_at_utc':status['collection_finished_at_utc'],'scope':{'tickers':list(ASSETS),'sources':['Naver Finance','Daum Finance'],'window':f"{iso(cutoff)} through {iso(now)}"},'method':status['method'],'observed_routes':{'naver':NAVER,'daum_page':DAUM_PAGE},'pagination':{'naver':'offset=prior result.lastOffset, max 5 pages/ticker, 0.55s delay'},'raw_evidence':'data/raw/kr_public/','normalized_csv':'data/normalized/kr_posts.csv','blockers':[status['sources'][f'daum_finance:{t}']['access_failure'] for t in ASSETS]}
 (norm/'kr_collection_provenance.json').write_text(json.dumps(prov,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'records':len(cleanrows),'counts':status['count_by_ticker_source'],'window':{'cutoff_utc':iso(cutoff),'now_utc':iso(now)}},ensure_ascii=False))
if __name__=='__main__':main()
