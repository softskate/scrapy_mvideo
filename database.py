import datetime
import uuid
from peewee import SqliteDatabase, Model, CharField, TextField, \
    DateTimeField, ForeignKeyField, IntegerField, UUIDField, BooleanField
import os


current_dir = os.path.dirname(os.path.abspath(__file__))
db = SqliteDatabase(os.path.join(current_dir, 'data.db'), pragmas={'journal_mode': 'wal'}, check_same_thread=False)

class BaseModel(Model):
    class Meta:
        database = db


class ParsingItem(BaseModel):
    user_id = CharField()
    link = CharField(unique=True)


class App(BaseModel):
    appid = UUIDField(primary_key=True, default=uuid.uuid4)
    name = CharField()
    start_url = CharField()


class Crawl(BaseModel):
    crawlid = UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = DateTimeField(default=datetime.datetime.now)
    finished = BooleanField(default=False)


class Product(BaseModel):
    appid = ForeignKeyField(App)
    crawlid = ForeignKeyField(Crawl)
    productId = CharField(16)
    imageUrls = TextField()
    name = CharField()
    price = IntegerField()
    brandName = CharField(null=True)
    details = TextField()
    productUrl = TextField()


if __name__ == "__main__":
    db.connect()
    db.create_tables(BaseModel.__subclasses__())
