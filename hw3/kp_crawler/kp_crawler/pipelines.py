# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

import base64
from io import BytesIO
from PIL import Image

import aiohttp
from aiohttp.client_exceptions import InvalidUrlClientError
import pymongo


class MongoPipeline:
    def __init__(self, mongo_uri, mongo_db):
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mongo_uri=crawler.settings.get('MONGO_URI'),
            mongo_db=crawler.settings.get('MONGO_DATABASE', 'items')
        )

    def open_spider(self, spider):
        self.client = pymongo.MongoClient(self.mongo_uri)
        self.db = self.client[self.mongo_db]

    def close_spider(self, spider):
        self.client.close()

    def process_item(self, item, spider):
        self.db['articles'].insert_one(dict(item))
        return item


class PhotoDownloaderPipeline:
    def __init__(self, result_image_quality: int):
        self.result_image_quality = result_image_quality

    @classmethod
    def from_crawler(cls, crawler):
        result_image_quality = crawler.settings.get("RESULT_IMAGE_QUALITY", 35)
        return cls(result_image_quality=result_image_quality)

    def compress_image(self, image_content: bytes):
        input_buffer = BytesIO(image_content)
        output_buffer = BytesIO()
        img = Image.open(input_buffer)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(output_buffer, format="JPEG", quality=self.result_image_quality, optimize=True)
        return output_buffer.getvalue()

    async def _download_photo_to_base64(self, url: str):
        async with aiohttp.ClientSession() as session:
            response = await session.get(url)
            if response.status != 200:
                return ""
            content = await response.read()
            compressed_bytes = self.compress_image(image_content=content)
            encoded_image = base64.b64encode(compressed_bytes).decode("utf-8")
            return encoded_image

    async def process_item(self, item, spider):
        if item["header_photo_url"]:
            try:
                photo_base64 = await self._download_photo_to_base64(item["header_photo_url"])
            except InvalidUrlClientError:
                item["header_photo_url"] = None
                return item
            item["header_photo_base64"] = photo_base64
            return item
        return item
