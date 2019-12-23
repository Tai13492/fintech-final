from configparser import SafeConfigParser
import pandas as pd

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.interfaces import PoolListener
from sqlalchemy.ext.declarative import declarative_base

from model.base import Base

from influxdb import InfluxDBClient


class ForeignKeysListener(PoolListener):
    def connect(self, dbapi_con, con_record):
        db_cursor = dbapi_con.execute('pragma foreign_keys=ON')


class DBClient:
    def __init__(self, db_type, opt=None):
        self.config = SafeConfigParser()
        self.opt = opt

        # config.ini should be same place to executing file
        self.config.read("config.ini")
        self.db_type = db_type
        self.connector = self.establish_connection_to_db()

        if self.is_influxdb() is not True:
            Session = sessionmaker(self.connector)
            self.session = Session()

            Base.metadata.create_all(bind=self.connector)

    def is_mysql(self):
        return self.db_type == "mysql"

    def is_sqlite3(self):
        return self.db_type == "sqlite3"

    def is_influxdb(self):
        return self.db_type == "influxdb"

    def establish_connection_to_db(self):
        if self.is_sqlite3():
            return self.sqlite3_establish_connection()
        elif self.is_mysql:
            return self.mysql_establish_connection()
        elif self.is_influxdb():
            return self.influxdb_establish_connection()

    def sqlite3_establish_connection(self):
        if self.opt == None:
            return create_engine("sqlite:///" + self.config['sqlite3']['db_path'], listeners=[ForeignKeysListener()])
        else:
            return create_engine("sqlite:///" + self.opt, listners=[ForeignKeysListener()])

    def mysql_establish_connection(self):
        if self.opt == None:
            conf = self.config['mysql']
            url = "mysql+pymysql://" + \
                conf['username'] + ":" + conf['password'] + \
                "@" + conf['host'] + "/" + conf['db_name']
            return create_engine(url, echo=True)

    def influxdb_establish_connection(self):
        return InfluxDBClient(
            host=self.config['influxdb']['host'],
            port=int(self.config['influxdb']['port']),
            username=self.config['influxdb']['username'],
            password=self.config['influxdb']['password']
        )

    # sqlite3
    def write_to_table(self, table_name, dataframe, if_exists):
        if self.is_influxdb() is not True:
            dataframe.to_sql(table_name, self.connector,
                             if_exists=if_exists, index=False)

    def overwrite_to_table(self, table_name, dataframe):
        self.write_to_table(table_name, dataframe, if_exists="replace")

    def append_to_table(self, table_name, dataframe):
        self.write_to_table(table_name, dataframe, if_exists="append")

    def is_table_exist(self, table_name):
        if self.is_sqlite3():
            query = "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='{}';".format(
                table_name)
            results = self.exec_sql(query, return_df=False)
            for result in results:
                if result == (1,):
                    return True
                else:
                    return False

        if self.is_mysql():
            query = "SHOW TABLES LIKE '" + table_name + "';"
            results = self.exec_sql(query, return_df=False)
            for result in results:
                if result == (table_name,):
                    return True
                else:
                    return False

        if self.is_influxdb():
            pass

    def get_row_by_id(self, table_name, id, return_type):
        if self.is_sqlite3():
            query = "SELECT * FROM " + table_name + \
                " WHERE id = " + str(id) + ";"
        return_df = pd.read_sql_query(
            query, self.connector, index_col="id")
        if return_df.empty is not True:
            return return_df
        else:
            return False

    def get_last_row(self, table_name):
        id = "(SELECT MAX(id) FROM " + table_name + ")"
        return self.get_row_by_id(table_name, id, return_type="dataframe")

    def exec_sql(self, query, return_df=True):
        if self.is_influxdb() is not True:
            if return_df:
                return pd.read_sql(query, self.connector, index_col="id")
            else:
                result_rows = self.connector.execute(query)
                return result_rows
