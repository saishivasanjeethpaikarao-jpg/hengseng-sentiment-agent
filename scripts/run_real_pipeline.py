#!/usr/bin/env python3
"""Analyze collected real files offline. No API/network calls are made here."""
from __future__ import annotations
import base64,html,json
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from cwt_sentiment.features import build_training_frame, MODEL_FEATURES, deduplicate_events
from cwt_sentiment.levels import community_levels
from cwt_sentiment.model import chronological_folds
from cwt_sentiment.sentiment import score_sentiment,direction_from_score

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/normalized';OUT=ROOT/'reports/real_run'
PRICE_FEATURES=['return_1d','return_5d','volatility_5d']
MARKETS={'HKEX':('Asia/Hong_Kong','16:10'),'KRX':('Asia/Seoul','15:40')}


def model():
    return make_pipeline(SimpleImputer(strategy='constant',fill_value=0),StandardScaler(),Ridge(alpha=1.0))


def summarize(predictions):
    actual=predictions.target_return.to_numpy(float);pred=predictions.predicted_return.to_numpy(float)
    return {'n_test':len(actual),'test_dates':int(predictions.date.nunique()),
            'test_start':str(predictions.date.min()),'test_end':str(predictions.date.max()),
            'mae_return':float(np.mean(np.abs(actual-pred))),
            'zero_baseline_mae':float(np.mean(np.abs(actual))),
            'directional_accuracy':float(np.mean(np.sign(actual)==np.sign(pred)))}


def evaluate(frame,features,splits):
    labeled=frame.dropna(subset=['target_return',*PRICE_FEATURES]).copy();parts=[];folds=[]
    for number,(train,test) in enumerate(chronological_folds(labeled,splits),1):
        if train.empty or test.empty:continue
        assert str(train.next_date.max())<str(test.date.min())
        fit=model().fit(train[features],train.target_return)
        out=test[['ticker','date','next_date','close','target_close','target_return']].copy()
        out['predicted_return']=fit.predict(test[features]);out['predicted_close']=out.close*np.exp(out.predicted_return);out['fold']=number
        parts.append(out);folds.append(dict(fold=number,train_start=str(train.date.min()),train_end=str(train.date.max()),train_target_end=str(train.next_date.max()),**summarize(out)))
    if not parts:raise ValueError('No eligible purged OOS folds')
    predictions=pd.concat(parts,ignore_index=True)
    return pd.DataFrame(folds),predictions,summarize(predictions)


def predict(train,latest,features):
    train=train.dropna(subset=['target_return',*PRICE_FEATURES]).copy()
    if train.empty:raise ValueError('No eligible training history')
    latest=latest.sort_values(['ticker','date']).groupby('ticker').tail(1).copy()
    assert latest.target_return.isna().all()
    fit=model().fit(train[features],train.target_return)
    out=latest[['ticker','date','close']].copy();out['predicted_return']=fit.predict(latest[features]);out['predicted_close']=out.close*np.exp(out.predicted_return)
    return out


def table(frame):
    return frame.to_html(index=False,escape=True,border=0,na_rep='Not available',float_format=lambda x:f'{x:,.3f}')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    assets=pd.read_csv(ROOT/'config/assets.csv');prices=pd.read_csv(DATA/'prices.csv');quotes=pd.read_csv(DATA/'quotes.csv');news=pd.read_csv(DATA/'news_public.csv')
    posts=pd.concat([pd.read_csv(DATA/'hk_posts.csv'),pd.read_csv(DATA/'kr_posts.csv')],ignore_index=True)
    before=len(posts);posts=deduplicate_events(posts,'timestamp_utc');posts['text']=posts.text.fillna('').astype(str)
    posts['sentiment']=posts.text.map(score_sentiment)
    posts.to_csv(DATA/'posts_all.csv',index=False)
    assert not prices.duplicated(['ticker','date']).any()
    assert pd.to_numeric(prices.close).gt(0).all()
    assert quotes.ticker.nunique()==len(assets)
    quality={'run_utc':datetime.now(timezone.utc).isoformat(),'prices_rows':len(prices),'prices_date_start':str(prices.date.min()),'daily_bar_latest_date':str(prices.date.max()),'posts':len(posts),'post_duplicates_removed':before-len(posts),'news':len(news),'quote_snapshots':len(quotes),'quote_daily_closes_missing':int(quotes.daily_bar_close_missing.sum()),'missing_followers':int(posts.author_followers.isna().sum()) if 'author_followers' in posts else len(posts),'spend_usd':0,'exa_called':False,'apify_run':False}
    quality['missing_telemetry']={field:int(posts[field].isna().sum()) if field in posts else len(posts) for field in ['likes','reposts','views','author_followers']}
    quality['timezone_assumptions']='Naive Naver/Daum site timestamps were explicitly interpreted as Asia/Seoul; source-clock accuracy was not independently certified.'
    coverage=[]
    for asset in assets.to_dict('records'):
        expected=['Moomoo','LIHKG'] if asset['market']=='HKEX' else ['Naver Finance','Daum Finance']
        actual=posts.loc[posts.ticker.eq(asset['ticker'])]
        for source in expected:
            key='naver' if source.startswith('Naver') else 'daum' if source.startswith('Daum') else source.lower()
            sample=actual.loc[actual.source.astype(str).str.lower().str.contains(key,regex=False)]
            coverage.append(dict(market=asset['market'],ticker=asset['ticker'],source=source,retained_records=len(sample),first_utc=sample.timestamp_utc.min() if len(sample) else '',last_utc=sample.timestamp_utc.max() if len(sample) else '',coverage_status='sample retained (not exhaustive)' if len(sample) else 'no retained records; see collection status'))
    coverage=pd.DataFrame(coverage);coverage.to_csv(OUT/'coverage.csv',index=False)
    levels=community_levels(posts,quotes);levels.to_csv(OUT/'community_level_evidence.csv',index=False)
    # A quoted market price is real data, but it is not silently substituted into official history.
    provisional=quotes[['ticker','quote_date_local','price','currency','data_source']].rename(columns={'quote_date_local':'date','price':'close'}).copy()
    provisional['bar_status']='provisional latest quote; not official daily close'
    historical=prices.copy();historical['bar_status']='daily bar with non-null source close'
    augmented=pd.concat([historical,provisional],ignore_index=True).sort_values(['ticker','date']).drop_duplicates(['ticker','date'],keep='last')
    augmented.to_csv(DATA/'prices_with_provisional_quote.csv',index=False)
    summaries={};all_forecasts=[];all_checks=[];experimental=[]
    for market,(tz,cutoff) in MARKETS.items():
        tickers=assets.loc[assets.market.eq(market),'ticker'];social=posts.loc[posts.ticker.isin(tickers)];headlines=news.loc[news.ticker.isin(tickers)]
        frame=build_training_frame(prices.loc[prices.ticker.isin(tickers)],social,headlines,tz,cutoff)
        frame.to_csv(OUT/f'{market}_features_daily_bar_history.csv',index=False)
        folds,predictions,summary=evaluate(frame,PRICE_FEATURES,4)
        folds.to_csv(OUT/f'{market}_price_only_fold_metrics.csv',index=False);predictions.to_csv(OUT/f'{market}_price_only_oos.csv',index=False)
        summary.update(model='pooled Ridge alpha=1; price-only',features=PRICE_FEATURES,warning='This long history validates price features only, not a sentiment edge.')
        summaries[market]={'price_only_oos':summary}
        # Retrospective next-session check: as of last official daily bar; held-out quote is not fitted.
        check=predict(frame,frame,PRICE_FEATURES).rename(columns={'date':'feature_date','close':'asof_close','predicted_close':'predicted_next_price'})
        check=check.merge(quotes[['ticker','price','quote_timestamp_utc','quote_date_local']],on='ticker').rename(columns={'price':'observed_provisional_quote'})
        check['actual_log_return']=np.log(check.observed_provisional_quote/check.asof_close)
        check['absolute_price_error']=(check.predicted_next_price-check.observed_provisional_quote).abs()
        check['direction_correct']=np.sign(check.predicted_return).eq(np.sign(check.actual_log_return))
        check['evaluation_type']='retrospective as-of holdout; outcome is provisional post-close quote, not official close'
        all_checks.append(check)
        # Current provisional-as-of forecast. Fit ONLY non-null source daily-bar history; no provisional target is fitted.
        live_frame=build_training_frame(augmented.loc[augmented.ticker.isin(tickers)],social,headlines,tz,cutoff)
        live_frame.to_csv(OUT/f'{market}_features_provisional_latest.csv',index=False)
        forecast=predict(frame,live_frame,PRICE_FEATURES);forecast['market']=market;forecast['model']='price-only benchmark';forecast['basis']='provisional latest quote; next exchange session date not independently calendar-verified'
        all_forecasts.append(forecast)
        # Tiny sentiment study only where historical social signal actually exists across dates.
        event_start=pd.to_datetime(social.timestamp_utc,utc=True).min() if len(social) else pd.NaT
        start_date=event_start.tz_convert(tz).date().isoformat() if pd.notna(event_start) else '9999-12-31'
        recent=frame.loc[frame.date.ge(start_date)].copy()
        observed_dates=int(recent.loc[recent.post_observed.gt(0),'date'].nunique())
        recent_info={'feature_start':start_date,'sessions':int(recent.date.nunique()),'social_observed_rows':int(recent.post_observed.sum()),'social_observed_dates':observed_dates,'status':'not evaluated: insufficient historical social sessions','warning':'Bounded retrospective sample; missing collection is not neutral. Text editing/survivorship and incomplete source coverage remain.'}
        if recent.dropna(subset=['target_return']).date.nunique()>=5 and observed_dates>=4:
            try:
                folds_s,pred_s,small=evaluate(recent,MODEL_FEATURES,3)
                folds_s.to_csv(OUT/f'{market}_experimental_sentiment_folds.csv',index=False);pred_s.to_csv(OUT/f'{market}_experimental_sentiment_oos.csv',index=False)
                _,_,paired_price=evaluate(recent,PRICE_FEATURES,3)
                recent_info.update(status='exploratory only; too few sessions for a reliable edge claim',metrics=small,paired_price_only_metrics=paired_price)
                tiny=predict(recent,live_frame,MODEL_FEATURES);tiny['market']=market;tiny['model']='experimental short-window sentiment';tiny['basis']='tiny recent sample; provisional latest quote; no validated edge'
                experimental.append(tiny)
            except ValueError as exc:recent_info['status']='not evaluated: '+str(exc)
        summaries[market]['short_sentiment_experiment']=recent_info
    forecasts=pd.concat(all_forecasts+experimental,ignore_index=True);forecasts['predicted_simple_return_pct']=100*np.expm1(forecasts.predicted_return);forecasts.to_csv(OUT/'next_session_forecasts.csv',index=False)
    checks=pd.concat(all_checks,ignore_index=True);checks.to_csv(OUT/'retrospective_next_session_quote_check.csv',index=False)
    quality['models']=summaries
    (OUT/'summary.json').write_text(json.dumps(quality,indent=2),encoding='utf-8')
    # Data-driven visualizations, never simulated numbers.
    plt.style.use('seaborn-v0_8-whitegrid');fig,axes=plt.subplots(1,2,figsize=(13,5.2),gridspec_kw={'width_ratios':[1,1.7]})
    markets=list(MARKETS);x=np.arange(2);width=.34
    axes[0].bar(x-width/2,[100*summaries[m]['price_only_oos']['mae_return'] for m in markets],width,label='Ridge price-only',color='#4868b8')
    axes[0].bar(x+width/2,[100*summaries[m]['price_only_oos']['zero_baseline_mae'] for m in markets],width,label='Zero-return',color='#b4bfd7')
    axes[0].set_xticks(x,markets);axes[0].set_ylabel('Mean absolute log-return error (%)');axes[0].set_title('Purged expanding-window benchmark');axes[0].legend(fontsize=9)
    counts=posts.groupby(['ticker','source']).size().unstack(fill_value=0).reindex(assets.ticker,fill_value=0)
    counts=counts.rename(columns={'naver_finance':'Naver Finance','daum_finance':'Daum Finance'})
    counts.plot.barh(stacked=True,ax=axes[1],color=['#4868b8','#44a694','#d89e42','#9c70b4'][:len(counts.columns)])
    axes[1].set_title('Real retained public social sample');axes[1].set_xlabel('Records (bounded coverage, not market activity)');axes[1].set_ylabel('');axes[1].legend(fontsize=8)
    fig.tight_layout();fig.savefig(OUT/'validation_and_coverage.png',dpi=170);plt.close(fig)
    image=base64.b64encode((OUT/'validation_and_coverage.png').read_bytes()).decode()
    snapshot=[]
    for asset in assets.to_dict('records'):
        ticker=asset['ticker'];sample=posts.loc[posts.ticker.eq(ticker)];q=quotes.loc[quotes.ticker.eq(ticker)].iloc[0]
        score=float(sample.sentiment.mean()) if len(sample) else np.nan
        texts=' '.join(sample.text).lower();longs=sum(texts.count(t) for t in ('bullish','buy','看好','買入','매수'));shorts=sum(texts.count(t) for t in ('bearish','sell','看空','賣出','매도'))
        cues='Long/buy wording' if longs>shorts else 'Short/sell wording' if shorts>longs else 'Mixed or not detected'
        evidence=levels.loc[levels.ticker.eq(ticker)]
        lev=lambda kind:', '.join(evidence.loc[evidence.kind.eq(kind),'level'].drop_duplicates().head(3)) or 'Not detected'
        snapshot.append(dict(market=asset['market'],ticker=ticker,asset=asset['asset_name'],quote=float(q.price),currency=q.currency,quote_time_utc=q.quote_timestamp_utc,mentions=len(sample),news_headlines=int(news.ticker.eq(ticker).sum()),sentiment=score,direction=direction_from_score(score) if pd.notna(score) else 'No social data',position_cues=cues,support_cues=lev('support'),resistance_cues=lev('resistance'),sources=int(sample.source.nunique())))
    snapshot=pd.DataFrame(snapshot).sort_values(['market','mentions','sentiment'],ascending=[True,False,False]);snapshot.to_csv(OUT/'market_snapshot.csv',index=False)
    sections=[]
    for market in markets:
        sections.append(f'<h2>{market}: ranked social snapshot</h2><div class="scroll">'+table(snapshot.loc[snapshot.market.eq(market)].drop(columns='market'))+'</div>')
    metric_table=pd.DataFrame([{'market':m,**{k:v for k,v in summaries[m]['price_only_oos'].items() if k in ['n_test','test_dates','mae_return','zero_baseline_mae','directional_accuracy']}} for m in markets])
    metric_table[['mae_return','zero_baseline_mae','directional_accuracy']]*=100
    metric_table=metric_table.rename(columns={'mae_return':'MAE log return (%)','zero_baseline_mae':'No-change MAE (%)','directional_accuracy':'Direction accuracy (%)'})
    body=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Real-data sentiment research prototype</title><style>body{{font:15px system-ui,sans-serif;line-height:1.55;background:#f3f5f9;color:#172039;margin:0}}main{{max-width:1250px;margin:auto;padding:24px}}h1{{line-height:1.15}}h2{{margin-top:34px}}.warning{{padding:18px;background:#fff1cf;border-left:5px solid #c78919;border-radius:8px}}.card,.scroll{{background:white;padding:16px;border-radius:12px;margin:16px 0;overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #e4e8f0;white-space:nowrap}}th{{color:#53617b}}img{{width:100%;height:auto}}small{{color:#58647a}}code{{background:#e4e9f1;padding:2px 5px}}a{{color:#335bb1}}</style><main><h1>HKEX + KRX: real-data research prototype</h1><p>10 assets · {len(posts):,} public social records · {len(news)} news headlines · {len(prices):,} daily bars · $0 external spend</p><div class="warning"><b>Working prototype — Apify and Exa runs are still outstanding.</b> No Apify Actor was run and no Exa search was made in this run, because no API keys are available in this environment; Google News RSS is a headline-only Exa substitute. The sentiment scorer is negation-aware with a hand-labelled accuracy check, and the frozen inputs are shipped in docs/frozen-run-2026-11-14/ so this run reproduces from a clean clone. Source samples are incomplete; any zero-coverage rows must not be read as neutral sentiment. Latest source daily close fields are null, so current prices and future forecasts use separately labelled provisional quote snapshots.</div><div class="card"><img alt="Actual benchmark errors and retained source counts" src="data:image/png;base64,{image}"></div><h2>What was actually validated</h2><p>The two-year result below is <b>price-only</b>, using pooled Ridge regression and four expanding date-grouped folds. Training targets end strictly before test feature dates. A lower error is better. <b>Neither market beat the no-change baseline.</b> The tiny sentiment runs also lost to no change and cover only three test dates. No predictive edge was established.</p><div class="scroll">{table(metric_table)}</div>{''.join(sections)}<p><small>Rankings are retained-sample counts, not total market activity. All {quality['missing_followers']:,} author-follower values are unavailable, not zero. </small></p><p><small>Sentiment is a small English/Chinese/Korean keyword baseline, not a validated language model. Position and explicit-money price levels are conservative, unverified wording cues, not portfolio positions or technical advice. Evidence is in community_level_evidence.csv. Cumulative engagement is descriptive only; it is excluded from backtest predictors.</small></p><h2>Provisional next-session point forecasts</h2><p>Generated now, after the quoted session, for the next exchange session. The quote is not silently labelled an official close. These outcomes are not yet observed. These are research estimates, not trading recommendations. Experimental sentiment forecasts, if present, have too little history for a reliable edge claim.</p><div class="scroll">{table(forecasts[['market','ticker','date','close','model','predicted_close','predicted_simple_return_pct']])}</div><h2>Retrospective one-session check</h2><p>Trained without the forecast feature row and checked against the subsequent post-close quote. This was generated retrospectively, not a prediction recorded before the market moved; outcome quotes remain provisional.</p><div class="scroll">{table(checks[['ticker','feature_date','asof_close','predicted_next_price','observed_provisional_quote','absolute_price_error','direction_correct']])}</div><h2>Coverage</h2><div class="scroll">{table(coverage)}</div><h2>How to explain this honestly</h2><p>“I built an auditable pipeline from UTC-tagged public events to exchange-local features and next-session returns. I evaluated a price benchmark with purged chronological splits. The sentiment experiment is limited by ten-day, uneven source coverage; I have not established a predictive sentiment edge. Under a zero-dollar constraint, I documented the Apify/Exa substitutions rather than pretending to meet them.”</p><p><a href="https://github.com/saishivasanjeethpaikarao-jpg/hengseng-sentiment-agent">Source repository</a> · See RUN_RESULTS.md and LEARNING_GUIDE.md in the package.</p></main></html>'''
    (OUT/'dashboard.html').write_text(body,encoding='utf-8')
    lines=['# What the real-data run found','',f'Collected **{len(posts):,} real public social records**, **{len(news)} news headlines**, **{len(prices):,} daily price bars**, and **10 latest quote snapshots** at **$0 external spend**. These are real records, not generated examples.','', '## The important caveat','', '**Apify and Exa runs are still outstanding.** No Apify Actor was run and no Exa search was made in this run, because no API keys are available in this environment; the free-credit balance of either account is unverified. Public local collection and Google News RSS are explicitly documented substitutes. The coverage table shows which source/ticker pairs actually yielded records; bounded samples are not exhaustive ten-day archives. Latest daily close fields are missing at the source; latest prices are separately labelled provisional quotes, not fabricated closes. The frozen inputs for this run are shipped in `docs/frozen-run-2026-11-14/` with a SHA256 manifest, so the numbers below reproduce from a clean clone.','', '## What the validation says','', 'The long-history experiment validates price features only. It uses a fixed Ridge model (alpha=1), pooled per market, and four expanding chronological folds with a conservative one-session target purge. No hyperparameters were selected after seeing the test results.','']
    lines += ['**The no-change baseline won in both markets.** Neither long-history price model established an edge; the tiny sentiment runs also lost to no change. Producing a point prediction is not evidence of predictive value.','',f"All {quality['missing_followers']:,} author-follower counts are unavailable and remain null. Missing telemetry counts: {quality['missing_telemetry']}. Naver/Daum naive site timestamps were explicitly interpreted as Asia/Seoul; source-clock accuracy was not independently certified.",'']
    for market in markets:
        s=summaries[market]['price_only_oos'];e=summaries[market]['short_sentiment_experiment']
        lines += [f"### {market}",f"Price-only OOS: **{s['n_test']:,} predictions across {s['test_dates']} dates** ({s['test_start']}–{s['test_end']}). MAE: **{100*s['mae_return']:.3f}% log return**; zero-return benchmark: **{100*s['zero_baseline_mae']:.3f}%**; directional accuracy: **{100*s['directional_accuracy']:.1f}%**.",'',f"Sentiment study: {e['status']}. Social observations cover {e['social_observed_dates']} historical feature dates and {e['social_observed_rows']} ticker-date rows. This is not enough to claim a durable edge.",'']
        if 'metrics' in e:
            sm=e['metrics'];pm=e['paired_price_only_metrics'];lines += [f"Tiny paired experiment: {sm['n_test']} test rows across {sm['test_dates']} dates; sentiment-feature MAE {100*sm['mae_return']:.3f}%, same-window price-only MAE {100*pm['mae_return']:.3f}%, zero-return MAE {100*sm['zero_baseline_mae']:.3f}%. Treat as a demonstration, not a finding of predictive superiority.",'']
    lines += ['## Current forecast versus checked history','',f"Yahoo daily bars with non-null source closes end on **{prices.date.max()}**. The retrospective next-session check is in `reports/real_run/retrospective_next_session_quote_check.csv`; its outcomes are post-close quote snapshots, not confirmed daily closes. It is a retrospective holdout, not a live prediction made in advance.",'', '`reports/real_run/next_session_forecasts.csv` contains new next-session point forecasts based on the current provisional quotes. Those future outcomes cannot be checked yet. The next session date has not been independently checked against an official holiday calendar. These are research outputs, not trading recommendations.','', '## Source coverage','',coverage[['market','ticker','source','retained_records']].to_markdown(index=False),'','Zero means no retained records in this bounded collection, **not** proof that no discussions exist. Moomoo is a public linked-post sample. LIHKG records marked `thread_title_only` are titles, not complete reply threads. See the source status JSONs and row-level record types.','', '## Reproduce and learn','', '1. Install the package and optional public dependencies; run `pytest -q`.','2. Inspect `data/normalized/` and each collection-status JSON.','3. Run `python scripts/run_real_pipeline.py` to regenerate all analysis offline.','4. Open `reports/real_run/dashboard.html`, then inspect the CSV predictions against the raw inputs.','5. Read `LEARNING_GUIDE.md`; practice explaining cutoff timing, missingness, baseline comparison, and why the source substitutions matter.','', '## What remains before calling it submission-ready','', 'Run the Apify Actor (scripts/run_apify_collection.py, needs APIFY_API_TOKEN) and the Exa news pull (scripts/run_exa_news.py, needs EXA_API_KEY) and record the Actor ID, run ID and request logs; until then the submission cannot claim Apify/Exa use. Resolve any remaining source/ticker gaps and extend the bounded samples to genuine ten-day coverage. Collect a longer as-of social archive; use official daily close data and a verified exchange calendar; re-run the same frozen evaluation. Do not hide these gaps in an interview.','', 'Source links are retained in the collected CSV rows and provenance files. Relevant public surfaces: [LIHKG](https://lihkg.com/category/15), [Moomoo](https://www.moomoo.com/stock/00700-HK/community), [Naver](https://m.stock.naver.com/domestic/stock/005930/discussion), [Daum](https://m.finance.daum.net/quotes/A005930/talks), [Google News](https://news.google.com/), [Yahoo Finance chart](https://query1.finance.yahoo.com/v8/finance/chart/0700.HK?range=1mo&interval=1d).']
    (ROOT/'RUN_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(quality,indent=2));print('REPORT',OUT/'dashboard.html',flush=True)

if __name__=='__main__':main()
