import json
from base64 import b64encode
import time
import requests
from urllib.parse import parse_qs, urlsplit
from database import Product, Crawl
from keys import URL


CHAT_ID = -4125682328

class Parser:
    @staticmethod
    def get_jhash(b):
        x = 123456789
        k = 0
        for i in range(1677696):
            x = ((x + b) ^ (x + (x % 3) + (x % 17) + b) ^ i) % 16776960
            if x % 117 == 0:
                k = (k + 1) % 1111
        return k
    
    def __init__(self) -> None:
        self.init()

    def init(self):
        self.sess = requests.Session()
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9',
            'Dnt': '1',
            'Priority': 'u=0, i',
            'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        }
        self.sess.headers.update(headers)
        while True:
            resp = self.sess.get('https://www.mvideo.ru')
            if resp.history: break

            code, age, sec, disable_utm = resp.cookies['__js_p_'].split(',')[:4]
            
            jhash = self.get_jhash(int(code))
            cookies = {
                '__jhash_': str(jhash),
                'max-age': age,
                'Path': '/',
                '__jua_': 'Mozilla%2F5.0%20%28Windows%20NT%2010.0%3B%20Win64%3B%20x64%29%20AppleWebKit%2F537.36%20%28KHTML%2C%20like%20Gecko%29%20Chrome%2F126.0.0.0%20Safari%2F537.36',
            }
            if sec:
                cookies['SameSite'] = 'None;Secure'

            for key, value in cookies.items():
                self.sess.cookies.set_cookie(requests.cookies.create_cookie(key, value, domain='www.mvideo.ru'))

        self.last_init = time.time()


    def make_req(self, *args, **kwargs):
        if 'json' in kwargs:
            resp = self.sess.post(*args, **kwargs)
        else:
            resp = self.sess.get(*args, **kwargs)
        
        if resp.status_code == 200:
            return resp.json().get('body')
        elif resp.status_code == 403:
            if time.time() - self.last_init < 20:
                time.sleep(10*60)
                
            time.sleep(10)
            self.init()
            return self.make_req(*args, **kwargs)

    def parse_product_list(self, url, appid, crawlid):
        splitted = url.split('?')[0].split('/')
        cat_id = splitted[4].split('-')[-1]

        params = {
            'categoryId': cat_id,
            'offset': 0,
            'limit': 24,
            'filterParams': ['WyJ0b2xrby12LW5hbGljaGlpIiwiLTEyIiwiZGEiXQ=='],
            'doTranslit': 'true'
        }

        for param in splitted[6:]:
            key, value = param.split('=')
            params['filterParams'].append(b64encode(json.dumps([key,"",value]).encode()).decode())

        query = urlsplit(url).query
        if query:
            query = parse_qs(query)
            for key, value in query.items():
                if key[:2] == 'f_':
                    key = key[2:]
                    for subvalue in value:
                        params['filterParams'].append(b64encode(json.dumps([key,"",subvalue]).encode()).decode())
        
        total = 24
        while params['offset'] < total:
            resp = self.make_req('https://www.mvideo.ru/bff/products/listing', params=params)

            self.parse_product_prices(resp['products'], url, appid, crawlid)

            total = resp['total']
            params['offset'] += params['limit']

            self.make_req('https://www.mvideo.ru/api/fl/idgib-w-mvideo')


    def parse_product_prices(self, product_ids, url, appid, crawlid):
        pl = {
            "productIds": product_ids,
            "mediaTypes":["images"],
            "category":True,
            "status":True,
            "brand":True,
            "propertyTypes":["KEY"],
            "propertiesConfig":{"propertiesPortionSize":20},
            "multioffer":False
        }
        self.sess.headers.update({'Referer': url})
        resp = self.make_req('https://www.mvideo.ru/bff/product-details/list', json=pl)
        prices_pl = {
            'productIds': ','.join(product_ids),
            'addBonusRubles': 'true',
            'isPromoApplied': 'true'
        }
        prices = self.make_req('https://www.mvideo.ru/bff/products/prices', params=prices_pl)
        prices = {x['productId']: x['price']['salePrice'] for x in prices['materialPrices']}

        for product in resp['products']:
            item = Product()
            item.appid = appid
            item.crawlid = crawlid
            item.productId = product['productId']
            item.imageUrls = json.dumps(['https://img.mvideo.ru/'+x for x in product['images']])
            item.name = product['name']
            item.price = prices[product['productId']]
            item.brandName = product['brandName']
            item.details = json.dumps({x['name']: x['value'] for x in product['propertiesPortion']})
            item.productUrl = 'https://www.mvideo.ru/products/' + product['nameTranslit'] + '-' + product['productId']
            item.save(True)
        
            
            latest_finished_crawl: Crawl = (
                Crawl
                .select()
                .where(Crawl.finished == True)
                .order_by(Crawl.created_at.desc())
                .first()
            )

            if latest_finished_crawl:
                old_ref = (
                    Product.select()
                    .where(
                        (Product.productId == item.productId)
                        & (Product.crawlid == latest_finished_crawl.crawlid))
                    .get_or_none()
                )
                if old_ref:
                    if (old_ref.price * .8) > item.price:
                        text = (
                            f"<b>MVideo</b>\n\n"
                            f"<b>Наименование:</b> <a href='{item.productUrl}'>{item.name}</a>\n"
                            f"<b>Старая цена</b>: {old_ref.price}\n<b>Цена</b>: {item.price}"
                        )
                        # Parameters to be sent with the request
                        params = {
                            'chat_id': CHAT_ID,
                            'text': text,
                            'parse_mode': 'HTML'
                        }

                        # Send the message
                        try:
                            response = requests.get(URL, params=params)
                            result = response.json()
                            if result['ok']:
                                print("Message sent successfully.")
                            else:
                                print("Failed to send message:", result['description'])
                        except Exception as e:
                            print(f"Failed to send message: {e}")
