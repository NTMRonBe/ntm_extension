import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _

class soa(osv.osv):
    _name = 'soa'
    _description = "Statement of Account"
    _columns = ""