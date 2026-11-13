# Historical source-discovery notes

These are the **pre-collection discovery notes**, preserved for provenance. Initial statements such as “unverified” or “no live dataset” below describe that earlier stage and are superseded by [RUN_RESULTS.md](RUN_RESULTS.md), [DATA_ACCESS.md](DATA_ACCESS.md), the source manifest, and actual collection-status JSONs. Local public collection was subsequently implemented; no Apify or Exa execution is implied.

## Assignment-listed source routes

- **LIHKG:** The [public category listing](https://lihkg.com/category/1) shows a finance section and a live thread list. The finance section is linked as `/category/15`; ticker-keyword retrieval and post-field completeness still need a custom-collector test. A third-party [LIHKG Apify actor listing](https://apify.com/claude_code_reviewer/lihkg-scraper-en/api/python) was not run.
- **Moomoo Community:** The public [Tencent 00700 community page](https://www.moomoo.com/stock/00700-HK/community) can be read through a rendered-page extraction and includes ticker-tagged posts, authors, timestamps, and text. A direct browser-style HTTP request returned an empty generic `Document` response without the ticker or post content. Treat Moomoo as **browser-rendering required and collector-unverified**; use it only if a custom browser Actor works without a paid proxy.
- **AAStocks / ETNet:** The tested [AAStocks forum URL](https://www.aastocks.com/en/stocks/analysis/forum.aspx?symbol=00700) returned page-not-found. The tested [ETNet Tencent quote page](https://www.etnet.com.hk/www/eng/stocks/realtime/quote.php?code=00700) showed market data and news/analysis, not a user-post discussion list.
- **Naver Finance:** The public [Naver hot discussion feed](https://m.stock.naver.com/discussion/home/hot) contains stock-tagged posts. The [per-stock discussion page](https://m.stock.naver.com/domestic/stock/005930/discussion) is client-loaded; the current frontend uses a `/front-api` prefix, but a stable unauthenticated ticker-feed endpoint was not verified.
- **Daum Finance:** The public [HiteJinro talks page](https://m.finance.daum.net/quotes/A000080/talks) exposes a ticker-specific post list with titles, authors, dates, views, recommendations, and a displayed total. It showed 1,065 posts and a current-post list, but the dynamic collection path still needs a repeatable test.
- **Telegram fallback checked:** The public [Ming Tak Finance channel](https://t.me/s/mingtak) is accessible, but the visible posts were mainly macro/gold analysis rather than a dependable feed for five HK-listed tickers. The public [Stock17168 channel](https://t.me/s/stock17168) focuses on Taiwan stocks, so it is not a suitable HK source for this assignment.

The tentative source pairs remain **LIHKG + Moomoo** for Hong Kong and **Naver + Daum** for Korea. None is yet an end-to-end Apify collector. If any candidate cannot be collected from a public page without paid Actors or proxies, choose another assignment-listed source only after verifying it; do not pretend the source worked.

## Official zero-cost limits

- [Apify pricing](https://apify.com/pricing) lists the Free plan at $0/month with $5 in monthly platform-usage credits. Custom Actor compute consumes platform usage. Recheck remaining included credits before building or running a custom Actor; no Store Actor or paid proxy may be used. No Actor was created, built, or run in this project.
- [Exa billing documentation](https://exa.ai/docs/admin/billing) lists $10 in Free-tier credits each month, says exhausted credits return `402 Payment Required`, and documents optional auto-recharge purchases. The user's remaining balance and auto-recharge state cannot be verified from the supplied standard API key, so no Exa request has been made. Use the Exa collector only after confirming both settings in the dashboard.
- Apify's read-only [monthly usage endpoint](https://docs.apify.com/api/v2/users-me-usage-monthly-get) and [limits endpoint](https://docs.apify.com/api/v2/users-me-limits-get) were used to check plan/usage status. No social scrape or account-setting change was made.

## Initial status (superseded by RUN_RESULTS.md)

No live social dataset, Exa results, forecasts, or performance metrics are claimed. A future collector must retain UTC timestamps and source URLs, respect a small request rate, deduplicate posts, and report missing author-follower data rather than invent it. Keep only public content and do not commit API keys or scraped datasets to the repository.
The documented read-only [monthly usage endpoint](https://docs.apify.com/api/v2/users-me-usage-monthly-get) and [limits endpoint](https://docs.apify.com/api/v2/users-me-limits-get) are appropriate for checking an account's allowance before a future run. No social scrape or account-setting change was made.
