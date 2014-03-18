import time
import datetime
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp
from stringprep import b1_set

class admin_backuprestoredb(osv.osv_memory):
	_name = 'admin.backuprestoredb'
	_description = "Database Administrative Function"
	'''def _get_db_list(self, cr, uid, ids, context=None):
		try:
			return rpc.session.execute_db('list') or []
		except:
			return []'''
			
	_columns = {
		'db_name':fields.char('Database Name',size=64, required=True),
		'db_func':fields.selection([('backup','Backup'),('restore','Restore')], 'Function'),
		'date':fields.date('Date'),
		'master_password':fields.char('Master Password', size=32, required=True),
		}
		
	
admin_backuprestoredb()
