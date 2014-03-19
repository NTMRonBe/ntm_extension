import time
import datetime
from osv import osv, fields, orm
import netsvc
import pooler
import os
import psycopg2
import tools
from tools.translate import _
import decimal_precision as dp
from stringprep import b1_set

class admin_backuprestoredb(osv.osv_memory):
	_name = 'admin.backuprestoredb'
	_description = "Database Administrative Function"
			
	_columns = {
		'db_name':fields.char('Database Name',size=64),
		'db_func':fields.selection([('backup','Backup'),('restore','Restore')], 'Function'),
		'date':fields.date('Date'),
		'new_db':fields.char('New Database Name',size=64),
		'backup_name':fields.char('Backup Name',size=64),
		'master_password':fields.char('Master Password', size=32),
		}
	
	def backup_restore(self, cr, uid, ids, context=None):
		for db in self.read(cr, uid, ids, context=None):
			if db['db_func']=='backup':
				self.createBackup(cr, uid, ids, context)
			elif db['db_func']=='restore':
				self.createRestore(cr, uid, ids, context)
		return {'type': 'ir.actions.act_window_close'}
			
	
	def createRestore(self, cr, uid, ids, context=None):
		configdb_password= tools.config['db_password']
		configdb_user = tools.config['db_user']
		configdb_host = tools.config['db_host']
		configdb_port = tools.config['db_port']
		print configdb_password
		print configdb_user
		print configdb_host
		print configdb_port
		if configdb_password==False:
			configdb_password = '1'
		if configdb_user == False:
			configdb_user = 'netadmin'
		if configdb_host==False:
			configdb_host = 'localhost'
		if configdb_port==False:
			configdb_port = '5432'
		for db in self.read(cr, uid, ids, context=None):
			ERPpassword = '1'
			dbName = db['new_db']
			backup = db['backup_name']
			outputdir = '/tmp/'
			outputdir = outputdir + backup
			dbhost='localhost'
			cmd = 'createdb -O %s %s; gunzip %s.backup.gz ; psql %s < %s.backup' %(configdb_user,dbName,outputdir,dbName,outputdir)
			print cmd
			os.system(cmd)
		return True
	
	def createBackup(self, cr, uid, ids, context=None):
		configdb_password= tools.config['db_password']
		configdb_user = tools.config['db_user']
		configdb_host = tools.config['db_host']
		configdb_port = tools.config['db_port']
		print configdb_password
		print configdb_user
		print configdb_host
		print configdb_port
		if configdb_password==False:
			configdb_password = '1'
		if configdb_user == False:
			configdb_user = 'netadmin'
		if configdb_host==False:
			configdb_host = 'localhost'
		if configdb_port==False:
			configdb_port = '5432'
		for db in self.read(cr, uid, ids, context=None):
			dbName =  db['db_name']
			outputdir = '/tmp/'
			outdbname = outputdir +db['db_name']+'_'+db['date'] +'.backup'
			dbhost='localhost'
			cmd = 'export PGPASSWORD=%s\npg_dump %s -U %s --file="%s" -h %s\ngzip -f %s' % (configdb_password, dbName, configdb_user, outdbname, configdb_host, outdbname)
			print cmd
			os.system(cmd)
		return True
	
admin_backuprestoredb()