import scrapy

class KpNewsItem(scrapy.Item):
    # Обязательные поля
    title = scrapy.Field()
    description = scrapy.Field()
    article_text = scrapy.Field()
    publication_datetime = scrapy.Field()
    keywords = scrapy.Field()
    authors = scrapy.Field()
    source_url = scrapy.Field()

    # Необязательные поля
    header_photo_url = scrapy.Field()
    header_photo_base64 = scrapy.Field()