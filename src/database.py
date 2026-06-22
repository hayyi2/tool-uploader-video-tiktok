# -------------------------------------------------------------------------
#
# Copyright 2009 Altra Studio
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
# -------------------------------------------------------------------------

"""
Disipakan dan dibuat untuk melakukan interaksi dengan database.
Jangan ada koneksi ke database pada file lain kecuali hanya pada file ini.
"""

import os
import json
import sqlite3

import qlobot_api

# -------------------------------------------------------------------------
# Abstract class
# -------------------------------------------------------------------------


class Connection:
    _connections = {}

    @staticmethod
    def dict_factory(cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def __init__(self):
        tool_id = qlobot_api.helpers.get_tool_id()
        path_data = os.path.join(qlobot_api.TOOLS_PATH, tool_id)
        if not os.path.isdir(path_data):
            os.mkdir(path_data)
        path_data_db = os.path.join(path_data, tool_id + '_data.db')
        self.file = path_data_db

    def __enter__(self):
        self.conn = sqlite3.connect(
            self.file, timeout=2, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = Connection.dict_factory
        self.the_cursor = self.conn.cursor()  # Tambahan sendiri: tain
        return self.the_cursor

    def __exit__(self, type, value, traceback):
        self.the_cursor.close()  # Tambahan sendiri: tain
        self.conn.commit()
        self.conn.close()


class BaseModel:
    _table_name = None
    _primary_key = 'id'
    _primary_type = 'INTEGER PRIMARY KEY AUTOINCREMENT'
    _time_format = r"%Y%m%d%H%M%S"
    _reference_fields = []

    _default_row = {}

    _default_data = []

    # _table_structure tidak perlu id, created_at, updated_at, meta
    _table_structure = [
    ]
    _adt_table_structure = [
    ]
    _timestamp: bool = False
    _created_at_column: str = 'created_at'
    _updated_at_column: str = 'updated_at'
    _meta = False  # string | false

    _last_update = 0

    @classmethod
    def setup(cls):
        if not cls.is_table_exists():
            cls.install()

    @classmethod
    def is_table_exists(cls):
        table_installed = 0

        with Connection() as db_cursor:
            db_cursor.execute(
                "SELECT count(name) as jumlah FROM sqlite_master " +
                "WHERE type='table' AND name='{}';".format(cls._table_name)
            )

            row = db_cursor.fetchone()
            table_installed = row["jumlah"]

        return table_installed > 0

    @classmethod
    def is_column_exists(cls, column: str):
        column_installed = 0

        with Connection() as db_cursor:
            db_cursor.execute(
                "SELECT count(*) > 0 as jumlah"
                "FROM pragma_table_info('{}') WHERE name='{}';".format(
                    cls._table_name, column)
            )

            row = db_cursor.fetchone()
            column_installed = row["jumlah"]

        return column_installed > 0

    @classmethod
    def add_columns(cls, columns):
        with Connection() as db_cursor:
            for column in columns:
                db_cursor.execute(
                    f"ALTER TABLE {cls._table_name} ADD COLUMN {column}")
        return True

    @classmethod
    def install(cls, set_default=True):
        cls._table_structure = [cls._primary_key +
                                ' ' + cls._primary_type] + cls._table_structure
        if cls._timestamp:
            cls._table_structure.append(
                cls._created_at_column + ' INTEGER NOT NULL')
            cls._table_structure.append(
                cls._updated_at_column + ' INTEGER NOT NULL')
        if cls._meta:
            cls._table_structure.append(
                cls._meta + ' TEXT DEFAULT \"{}\" NOT NULL')
        cls._table_structure += cls._adt_table_structure

        with Connection() as db_cursor:
            db_cursor.execute("CREATE TABLE IF NOT EXISTS {} ({});".format(
                cls._table_name, ', '.join(cls._table_structure)))

            if set_default and len(cls._default_data) > 0:
                cls.bulk_insert(cls._default_data)
        return True

    @classmethod
    def validate_row_column(cls, row_data: dict):
        available_keys = cls.get_default_row().keys()
        row_data = {_k: _v for _k, _v in row_data.items(
        ) if (
            _k in available_keys
            or _k == cls._primary_key
            or _k in cls._reference_fields
        )}
        return row_data

    @classmethod
    def get_default_row(cls):
        if cls._meta and cls._meta not in cls._default_row:
            cls._default_row[cls._meta] = {}
        return cls._default_row

    @classmethod
    def gets(cls):
        data = []
        with Connection() as cur:
            cur.execute("SELECT * FROM %s" % cls._table_name)
            data = cur.fetchall()

        if cls._meta:
            for item in data:
                item[cls._meta] = json.loads(item[cls._meta])

        return data

    @classmethod
    def gets_where(cls, column, value, operator="="):
        data = []
        with Connection() as cur:
            query = "SELECT * FROM %s WHERE %s %s %s" % (
                cls._table_name,
                column,
                operator, ":"+column
            )
            cur.execute(query, {column: value})
            data = cur.fetchall()

        if cls._meta:
            for item in data:
                item[cls._meta] = json.loads(item[cls._meta])

        return data

    @classmethod
    def gets_where_in(cls, column, value):
        data = []
        with Connection() as cur:
            query = (
                f"SELECT * FROM {cls._table_name} "
                f"WHERE {column} in ({','.join([str(_) for _ in value])})"
            )
            cur.execute(query)
            data = cur.fetchall()

        if cls._meta:
            for item in data:
                item[cls._meta] = json.loads(item[cls._meta])

        return data

    @classmethod
    def latest(cls, last_update=0):
        return cls.gets_where(cls._updated_at_column, last_update, '>')

    @classmethod
    def get_by_id(cls, the_id):
        data = {}
        with Connection() as cur:
            cur.execute("SELECT * FROM {} WHERE {}=:id".format(
                cls._table_name, cls._primary_key), {"id": str(the_id)},
            )
            data = cur.fetchone()

        if not data:
            return data

        if cls._meta:
            data[cls._meta] = json.loads(data[cls._meta])
        return data

    @classmethod
    def get_where(cls, column, value, operator="="):
        data = {}
        with Connection() as cur:
            query = "SELECT * FROM %s WHERE %s %s %s" % (
                cls._table_name, column, operator, ":"+column
            )
            cur.execute(query, {column: value})
            data = cur.fetchone()

        if not data:
            return data

        if cls._meta:
            data[cls._meta] = json.loads(data[cls._meta])
        return data

    @classmethod
    def get_last(cls):
        data = {}
        with Connection() as cur:
            cur.execute("SELECT * FROM {} ORDER BY {} DESC limit 1".format(
                cls._table_name, cls._primary_key))
            data = cur.fetchone()

        if not data:
            return data
        if cls._meta:
            data[cls._meta] = json.loads(data[cls._meta])
        return data

    @classmethod
    def get_last_update(cls):
        return cls._last_update

    @classmethod
    def insert(cls, row_data: dict):
        row_data = cls.validate_row_column(row_data)
        row_data = {**cls.get_default_row(), **row_data}
        insert_id = None
        if cls._timestamp:
            current_time = qlobot_api.helpers.current_datetime(
                cls._time_format)
            cls._last_update = current_time
            if cls._created_at_column not in row_data:
                row_data[cls._created_at_column] = current_time
            if cls._updated_at_column not in row_data:
                row_data[cls._updated_at_column] = current_time
        if cls._meta:
            row_data[cls._meta] = json.dumps(row_data[cls._meta])

        with Connection() as cur:
            columns = ', '.join(row_data.keys())
            placeholders = ':'+', :'.join(row_data.keys())

            cur.execute("INSERT INTO %s (%s) VALUES (%s)" %
                        (cls._table_name, columns, placeholders), row_data)
            insert_id = cur.lastrowid

        return insert_id

    @classmethod
    def bulk_insert(cls, data: list):
        for _i, _row in enumerate(data):
            _row = {**cls.get_default_row(), **_row}
            # validasi kolom yang editable
            _row = cls.validate_row_column(_row)
            if cls._timestamp:
                current_time = qlobot_api.helpers.current_datetime(
                    cls._time_format)
                cls._last_update = current_time
                if cls._created_at_column not in _row:
                    _row[cls._created_at_column] = current_time
                if cls._updated_at_column not in _row:
                    _row[cls._updated_at_column] = current_time
            if cls._meta:
                _row[cls._meta] = json.dumps(_row[cls._meta])
            data[_i] = _row

        with Connection() as cur:
            columns = ', '.join(data[0].keys())
            placeholders = ':'+', :'.join(data[0].keys())

            query = "INSERT INTO %s (%s) VALUES (%s)" % (
                cls._table_name, columns, placeholders)

            cur.executemany(query, data)

    @classmethod
    def update(cls, row_data: dict):
        if cls._primary_key not in row_data:
            raise Exception("Untuk melakukan update kolom id harus diisi")

        Id = row_data[cls._primary_key]
        row_data = cls.validate_row_column(
            row_data)  # validasi kolom yang editable
        row_data[cls._primary_key] = Id

        if cls._timestamp:
            current_time = qlobot_api.helpers.current_datetime(
                cls._time_format)
            cls._last_update = current_time
            if cls._updated_at_column not in row_data:
                row_data[cls._updated_at_column] = current_time
        if cls._meta and cls._meta in row_data:
            row_data[cls._meta] = json.dumps(row_data[cls._meta])

        with Connection() as cur:
            column_sql = ", ".join([i+"=:"+i for i in row_data.keys()])
            query = "UPDATE  %s SET %s WHERE %s=%s" % (
                cls._table_name,
                column_sql,
                cls._primary_key,
                ":"+cls._primary_key
            )

            cur.execute(query, row_data)

    @classmethod
    def bulk_update(cls, data: list):
        update_data = []
        for _i, _row in enumerate(data):
            item = {**_row}
            if cls._primary_key not in item:
                del data[_i]
                continue

            Id = item[cls._primary_key]
            # validasi kolom yang editable
            item = cls.validate_row_column(item)
            item[cls._primary_key] = Id

            if cls._timestamp:
                current_time = qlobot_api.helpers.current_datetime(
                    cls._time_format)
                cls._last_update = current_time
                if cls._updated_at_column not in item:
                    item[cls._updated_at_column] = current_time
            if cls._meta and cls._meta in item:
                item[cls._meta] = json.dumps(item[cls._meta])
            update_data.append(item)

        with Connection() as cur:
            column_sql = ", ".join([i+"=:"+i for i in update_data[0].keys()])

            query = "UPDATE %s SET %s WHERE %s=%s" % (
                    cls._table_name, column_sql, cls._primary_key,
                    ":"+cls._primary_key)

            cur.executemany(query, update_data)

    @classmethod
    def delete(cls, column, value, operator="="):
        with Connection() as cur:
            query = "DELETE FROM %s WHERE %s %s %s" % (
                cls._table_name, column, operator, ":"+column
            )
            placeholders = {column: value}
            cur.execute(query, placeholders)

    @classmethod
    def delete_by_id(cls, row_id):
        return cls.delete(cls._primary_key, row_id)

    @classmethod
    def bulk_delete_by_id(cls, row_ids):
        column = cls._primary_key
        placeholders = []
        for _id in row_ids:
            placeholders.append({column: _id})
        with Connection() as cur:
            query = "DELETE FROM %s WHERE %s %s %s" % (
                cls._table_name, column, '=', ":"+column)

            cur.executemany(query, placeholders)

    @classmethod
    def bulk_inser_or_update(cls, data: list, insert_key: list):
        update_data = []
        for _i, _row in enumerate(data):
            item = {**_row}
            if cls._primary_key not in item:
                del data[_i]
                continue

            Id = item[cls._primary_key]
            # validasi kolom yang editable
            item = cls.validate_row_column(item)
            item[cls._primary_key] = Id

            if cls._timestamp:
                current_time = qlobot_api.helpers.current_datetime(
                    cls._time_format)
                cls._last_update = current_time
                if cls._updated_at_column not in item:
                    item[cls._updated_at_column] = current_time
            if cls._meta and cls._meta in item:
                item[cls._meta] = json.dumps(item[cls._meta])
            update_data.append(item)

        with Connection() as cur:
            columns = ', '.join(update_data[0].keys())
            placeholders = ':'+', :'.join(update_data[0].keys())

            update_keys = []
            for key in update_data[0].keys():
                if key in insert_key:
                    continue
                update_keys.append(f"{key} = excluded.{key}")

            query = (
                f"INSERT INTO {cls._table_name} ({columns}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT({', '.join(insert_key)}) DO UPDATE SET "
                f"{', '.join(update_keys)};"
            )

            cur.executemany(query, update_data)


class BaseSetting:
    _table_name = 'settings'

    _default_data = {}

    @classmethod
    def get_connection(cls):
        return Connection()

    @classmethod
    def setup(cls):
        if not cls.is_table_exists():
            cls.install()

    @classmethod
    def is_table_exists(cls):
        table_installed = 0

        with Connection() as db_cursor:
            db_cursor.execute(
                "SELECT count(name) as jumlah FROM sqlite_master " +
                "WHERE type='table' AND name='{}';".format(cls._table_name)
            )

            row = db_cursor.fetchone()
            table_installed = row["jumlah"]

        return table_installed > 0

    @classmethod
    def install(cls, set_default=True):
        cls._table_structure = [
            'key TEXT PRIMARY KEY NOT NULL',
            'value TEXT NOT NULL'
        ]
        with Connection() as db_cursor:
            db_cursor.execute("CREATE TABLE IF NOT EXISTS {} ({});".format(
                cls._table_name, ', '.join(cls._table_structure)))

            if set_default and cls._default_data:
                cls.set(cls._default_data)
        return True

    @classmethod
    def gets_default(cls):
        return cls._default_data

    @classmethod
    def gets(cls):
        row_data = []
        with Connection() as cur:
            cur.execute("SELECT * FROM %s" % cls._table_name)
            row_data = cur.fetchall()

        data = {}
        for item in row_data:
            data[item['key']] = json.loads(item['value'])

        return {**cls._default_data, **data}

    @classmethod
    def get(cls, key: str):
        data = None
        with Connection() as cur:
            cur.execute(
                f"SELECT * FROM {cls._table_name} WHERE key=:key",
                {"key": key}
            )
            data = cur.fetchone()

        if not data:
            return cls._default_data.get(key)

        return json.loads(data['value'])

    @classmethod
    def set(cls, key, value=False):
        row_data = []
        if type(key) is dict:
            for _key, value in key.items():
                row_data.append({
                    'key': _key,
                    'value': json.dumps(value),
                })
        else:
            row_data.append({
                'key': key,
                'value': json.dumps(value),
            })
        with Connection() as cur:
            cur.executemany(
                f"INSERT INTO {cls._table_name} (key, value) "
                "VALUES (:key, :value) "
                "ON CONFLICT (key) DO "
                "UPDATE SET value=excluded.value;",
                row_data
            )

# -------------------------------------------------------------------------
# Concrete class
# -------------------------------------------------------------------------


class AccountModel(BaseModel):
    _table_name = 'accounts'

    _timestamp = True
    _created_at_column: str = 'created_at'
    _updated_at_column: str = 'updated_at'
    _meta = 'meta'

    _default_row = {
        'name': '',
        'username': '',
        'password': '',
        'loggenin': 0,
        'account_name': '',
        'account_username': '',
        'account_picture': '',
        'last_check_at': 0,
    }
    _table_structure = [
        "name text not null",
        "username TEXT NOT NULL",
        "password TEXT NOT NULL",
        "loggenin INTEGER DEFAULT 0 NOT NULL",
        "account_name TEXT DEFAULT '' NOT NULL",
        "account_username TEXT DEFAULT '' NOT NULL",
        "account_picture TEXT DEFAULT '' NOT NULL",
        "last_check_at INTEGER DEFAULT 0 NOT NULL",
    ]

    @classmethod
    def update(cls, account: dict):
        super().update(account)

        showcase = account.get('showcase')
        if not showcase:
            return

        account_showcase = ShowcaseModel.gets_where(
            'account_id', account['id']
        )
        account_showcase_id = {
            _['product_id']: _['id']
            for _ in account_showcase
        }

        showcase_ids = []
        for product in showcase:
            if product['product_id'] in account_showcase_id:
                showcase_ids.append(account_showcase_id[product['product_id']])
                ShowcaseModel.update({
                    'id': account_showcase_id[product['product_id']],
                    'account_id': account['id'],
                    **product,
                })
            else:
                showcase_id = ShowcaseModel.insert({
                    'account_id': account['id'],
                    **product,
                })
                showcase_ids.append(showcase_id)

        delete_showcase_ids = [
            _ for _ in account_showcase_id.values()
            if _ not in showcase_ids
        ]
        if delete_showcase_ids:
            ShowcaseModel.bulk_delete_by_id(delete_showcase_ids)

    @classmethod
    def gets_dict_with_products(cls):
        accounts = super().gets()
        accounts = [{**_, 'showcases': {}} for _ in accounts]
        accounts = {_['id']: _ for _ in accounts}
        products = ShowcaseModel.gets()
        for product in products:
            if product['account_id'] not in accounts:
                continue
            accounts[product['account_id']]['showcases'][product['id']] = product  # noqa

        return accounts


class ShowcaseModel(BaseModel):
    _table_name = 'showcases'

    _default_row = {
        'account_id': 0,
        'product_id': '',
        'product_url': '',
        'product_title': '',
        'product_thumb': '',
        'product_price': 0,
        'product_stock': 0,
        'product_commission': 0,
        'product_can_added': 0,
    }
    _table_structure = [
        (
            "account_id INTEGER NOT NULL "
            "REFERENCES accounts(id) ON DELETE CASCADE"
        ),
        "product_id text not null",
        "product_url TEXT NOT NULL",
        "product_title TEXT NOT NULL",
        "product_thumb TEXT NOT NULL",
        "product_price INTEGER DEFAULT 0 NOT NULL",
        "product_stock INTEGER DEFAULT 0 NOT NULL",
        "product_commission INTEGER DEFAULT 0 NOT NULL",
        "product_can_added BOOLEAN CHECK (product_can_added IN (0, 1))",
    ]


class ProjectModel(BaseModel):
    _table_name = 'projects'

    _timestamp = True
    _created_at_column: str = 'created_at'
    _updated_at_column: str = 'updated_at'
    _meta = 'meta'

    _default_row = {
        'name': '',
    }
    _table_structure = [
        "name text not null",
    ]

    @classmethod
    def gets_last_update(cls):
        data = []
        with Connection() as cur:
            cur.execute("SELECT * FROM {} ORDER BY {} DESC".format(
                cls._table_name,
                cls._updated_at_column
            ))
            data = cur.fetchall()

        if cls._meta:
            for item in data:
                item[cls._meta] = json.loads(item[cls._meta])

        return data


class VideoModel(BaseModel):
    _table_name = 'videos'

    _reference_fields = ['account_id']
    _default_row = {
        'project_id': 0,
        'video_path': '',
        'caption': '',
        'upload_status': 'pending',
        'uploaded_at': 0,
    }
    _table_structure = [
        (
            "project_id INTEGER NOT NULL "
            "REFERENCES projects(id) ON DELETE CASCADE"
        ),
        (
            "account_id INTEGER "
            "REFERENCES accounts(id) ON DELETE CASCADE"
        ),
        "video_path text not null",
        "caption text not null",
        "upload_status text default 'pending' not null",
        # pending, waiting, uploading, uploaded, cancel, failed
        "uploaded_at INTEGER DEFAULT 0 NOT NULL",
    ]

    @classmethod
    def update_showcase(cls, video):
        showcases = VideoShowcaseModel.gets_where('video_id', video['id'])
        showcase_ids = [_['showcase_id'] for _ in showcases]
        new_showcase_ids = video.get('showcase_ids', [])
        for showcase_id in new_showcase_ids:
            if showcase_id not in showcase_ids:
                VideoShowcaseModel.insert({
                    'video_id': video['id'],
                    'showcase_id': showcase_id,
                })
        delete_showcase_ids = [
            _['id'] for _ in showcases
            if _['showcase_id'] not in new_showcase_ids
        ]
        VideoShowcaseModel.bulk_delete_by_id(delete_showcase_ids)

    @classmethod
    def gets_project(cls, project_id, video_to_upload=False):
        videos = cls.gets_where('project_id', project_id)
        if video_to_upload:
            status_to_upload = ['pending', 'cancel', 'failed']
            videos = [
                _ for _ in videos
                if _['account_id'] and _['upload_status'] in status_to_upload
            ]

        videos = [{**_, 'showcase_ids': []} for _ in videos]
        video_ids = {_['id']: index for index, _ in enumerate(videos)}
        showcases = VideoShowcaseModel.gets_where_in(
            'video_id', video_ids.keys()
        )
        for showcase in showcases:
            videos[video_ids[showcase['video_id']]]['showcase_ids'].append(
                showcase['showcase_id']
            )
        if video_to_upload:
            account_ids = list(set([_['account_id'] for _ in videos]))
            accounts = AccountModel.gets_where_in('id', account_ids)
            accounts = {_['id']: _ for _ in accounts}
            for video in videos:
                video['account'] = accounts[video['account_id']]

            showcases_ids = list(set([_['showcase_id'] for _ in showcases]))
            showcase_products = ShowcaseModel.gets_where_in(
                'id', showcases_ids
            )
            for video in videos:
                video['showcase'] = [
                    _ for _ in showcase_products
                    if _['id'] in video['showcase_ids']
                ]

        return videos

    @classmethod
    def gets_ids(cls, video_ids):
        videos = cls.gets_where_in('id', video_ids)
        videos = [{**_, 'showcase_ids': []} for _ in videos]
        video_ids = {_['id']: index for index, _ in enumerate(videos)}
        showcases = VideoShowcaseModel.gets_where_in(
            'video_id', video_ids.keys()
        )
        for showcase in showcases:
            videos[video_ids[showcase['video_id']]]['showcase_ids'].append(
                showcase['showcase_id']
            )
        return videos

    @classmethod
    def get_by_id(cls, the_id):
        video = super().get_by_id(the_id)
        showcases = VideoShowcaseModel.gets_where('video_id', the_id)
        video['showcase_ids'] = [_['showcase_id'] for _ in showcases]
        return video


class VideoShowcaseModel(BaseModel):
    _table_name = 'video_showcases'

    _default_row = {
        'video_id': 0,
        'showcase_id': 0,
    }

    _table_structure = [
        (
            "video_id INTEGER DEFAULT 0 NOT NULL "
            "REFERENCES videos(id) ON DELETE CASCADE"
        ),
        (
            "showcase_id INTEGER DEFAULT 0 NOT NULL "
            "REFERENCES showcases(id) ON DELETE CASCADE"
        ),
    ]


def setup_database():
    AccountModel.setup()
    ShowcaseModel.setup()
    ProjectModel.setup()
    VideoModel.setup()
    VideoShowcaseModel.setup()
