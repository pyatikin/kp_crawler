import scrapy
from scrapy_playwright.page import PageMethod
from ..items import KpNewsItem
from lxml import html

class KpSpider(scrapy.Spider):
    name = 'kp_spider'
    start_urls = ['https://www.kp.ru/online/']
    custom_settings = {
        'CLOSESPIDER_ITEMCOUNT': 1000,  # Останавливаемся после сбора 1000 элементов
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        'TWISTED_REACTOR': "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 180000,  # Увеличиваем таймаут
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                meta={
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_selector', 'div.sc-1tputnk-13'),  # Ожидаем загрузки статей
                    ],
                    'playwright_include_page': True,  # Включаем доступ к странице Playwright
                },
                callback=self.parse,
                errback=self.errback,
            )

    async def parse(self, response):
        page = response.meta['playwright_page']
        articles_count = 0

        while articles_count < 1000:
            # Парсим текущие статьи
            articles = response.xpath('//div[contains(@class, "sc-1tputnk-13")]')
            for article in articles:
                item = KpNewsItem()
                item['title'] = self.clean_title(article.xpath('.//a[contains(@class, "sc-1tputnk-2")]').get())
                item['description'] = article.xpath('.//a[contains(@class, "sc-1tputnk-3")]/text()').get()
                item['source_url'] = response.urljoin(
                    article.xpath('.//a[contains(@class, "sc-1tputnk-2")]/@href').get()
                )

                # Переходим на страницу статьи
                yield scrapy.Request(
                    url=item['source_url'],
                    meta={'playwright': True, 'item': item},
                    callback=self.parse_article,
                    errback=self.errback,
                )

                articles_count += 1

                if articles_count >= 1000:
                    break

            if articles_count >= 1000:
                break

            # Пытаемся найти и нажать кнопку "Показать ещё"
            show_more_button = await page.query_selector('button.sc-abxysl-0.cdgmSL')
            if show_more_button:
                await show_more_button.click()
                await page.wait_for_selector('div.sc-1tputnk-13', timeout=10000)
                await page.wait_for_timeout(2000)

                html_content = await page.content()
                response = response.replace(body=html_content)
            else:
                break

        await page.close()

    def parse_article(self, response):
        item = response.meta['item']

        item['article_text'] = ' '.join(response.xpath('//p[contains(@class, "sc-1wayp1z-16")]//text()').getall())

        item['authors'] = response.xpath('//span[contains(@class, "sc-1jl27nw-1")]/text()').getall()

        key_fields = response.xpath('.//div[contains(@class, "sc-j7em19-2 dQphFo")]')
        if key_fields:
            item['keywords'] = key_fields.xpath('.//a[contains(@class, "sc-1vxg2pp-0 cXMtmu")]/text()').getall()
            item['publication_datetime'] = key_fields.xpath('.//span[contains(@class, "sc-j7em19-1 dtkLMY")]/text()').get()

        image = response.xpath('.//img[contains(@class, "sc-foxktb-1")]/@src').get()
        item['header_photo_url'] = image if image else None

        yield item

    def errback(self, failure):
        self.logger.error(repr(failure))

    def clean_title(self, raw_title):
        if not raw_title:
            return ""
        tree = html.fromstring(raw_title)
        cleaned_title = tree.text_content().strip()
        cleaned_title = " ".join(cleaned_title.split())
        return cleaned_title