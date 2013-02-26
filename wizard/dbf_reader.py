# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from osv import fields, osv
from tools.translate import _
from dbfpy import dbf
import csv
import sys
import netsvc
import os

class dbf_files(osv.osv):
    _name = 'dbf.files'
    _description = "DBF Files on Folder"
    _columns= {
        'name':fields.char('File Name',size=64,readonly=True),
        'user_id':fields.many2one('res.users','User',readonly=True),
        'imported':fields.boolean('File already imported',readonly=True),
        'extension':fields.selection([
                                      ('dbf','dbf'),
                                      ('DBF','DBF'),
                                      ],'File Extension',readonly=True),
        'full_location':fields.char('Full Location',size=100,readonly=True),
        'converted_file':fields.char('Converted File',size=100,readonly=True),
        }
     
dbf_files()
class dbf_details(osv.osv):
    _name = 'dbf.details'
    _description = "DBF Converted File Details"
    _columns = {
        'battypecd':fields.selection([
                                    ('CR','CASH RECEIPT'),
                                    ('CK','CONTRIBUTION IN KIND'),
                                    ('CD','CASH DISBURSEMENT'),
                                    ('AJ','ADJUSTING JOURNAL'),
                                    ('SJ','SALES JOURNAL'),
                                    ('TA','TRANSFER, AUTOMATED'),
                                    ('TD','TRANSFER, DAILY'),
                                    ('TM','TRANSFER, MONTHLY'),
                                    ('PJ','PAYABLES JOURNAL'),
                                    ('YC','YEAR END CLOSING BATCH'),
                                    ('WD','WIRE DISBURSEMENT'),
                                    ('TC','TRANSFER, CONSIGNMENT'),
                                    ('TI','TRANSFER, INSURANCE'),
                                    ('CC','CREDIT CARD BATCH')
                                      ],'BATTYPECD'),
        'batdt':fields.date('BATDT'),
        'trancd':fields.selection([
                            ('DG','DESIGNATED'),('PY','PAYMENT'),('BD','BIRTHDAY GIFT'),
                            ('PG','PERSONAL GIFT'),('DP','DEPOSIT TO PERSONAL'),('RF','REFUND'),
                            ('CH','CHRISTMAS GIFT'),('NT','POA, COUNTS AS INCOME'),('DO','DESIGNATED BY OFFICE'),
                            ('AD','AUTHORIZED DESIGNATED'),('ST','STUDENT GIFT'),('CK','CONTRIBUTION IN KIND'),
                            ('TI','TAXABLE INCOME'),('SU','SUBSIDY PAYMENT TAXABLE'),('AS','SUMMIT ASSIST, TAX-DEDUCT'),
                            ('IF','INTERFACE, NON-TAX-DEDUCT'),('GP','GIFT (FROM PERSONAL ACCT)'),('PD','PERSONAL DISBURSEMENT'),
                            ('SD','SPECIAL DISBURSEMENT'),('ME','MINISTRY EXPENSE'),('GS','GIFT (FROM SPECIAL ACCT)'),
                            ('DS','DEPOSIT TO SPECIAL'),('MI','MINISTRY INCOME'),('DD','ASSIST DISBURSMENT'),
                            ('PI','MEDICAL INSURANCE DEBITS'),('IN','SUMMIT INTERFACE INTERN'),('ID','INTERFACE DISBURSEMENT'),
                            ('MU','MAKEUP ALLOWANCE'),('MD','MINISTRY DISBURSEMENT'),('TS','403B TSA CONTRIBUTION'),
                            ('CL','CLEAR MISSION SUBACCOUNT'),('WD','WIRE DISBURSEMENT'),('DV','DEPOSIT TO VOUCHER'),
                            ('VD','VOUCHER DISBURSEMENT'),('HD','HOLDING DISBURSEMENT'),('HI','HOLDING INCOME'),
                            ('LI','LIFE INSURANCE DEBITS'),('LP','LIFE INSURANCE POST-TAX'),('V','VOUCHER'),('BI','BUDGET INCOME'),
                            ('BO','BUDGET DISBURSE OUT'),('TP','TRAINING ACCOUNT PAYMENT'),('TC','TRAINING CHARGE'),('EC','MEC EXPENSE CLAIM'),
                            ('ED','MEC EXPENSE DISBURSEMENT'),('MP','MINISTRY PROJECT INCOME'),('HP','HOLDING PROJECT INCOME'),('MX','MINISTRY (FIELD % EXEMPT)'),
                            ('MS','SOCIAL SECURITY TAX'),('MM','MEDICARE TAX'),('VO','VOID TRANSACTION'),('TR','403B ROTH CONTRIBUTION')
                            ],'TRANCD'),
        'docno':fields.char('DOCNO',size=6),
        'amount':fields.float('AMOUNT'),
        'batltr':fields.char('BATLTR',size=2),
        'comm1':fields.char('COMM1',size=25),
        'comm2':fields.char('COMM2',size=25),
        'dcno':fields.char('DCNO',size=6),
        'filename':fields.char('Filename',size=64,readonly=True),
        'period_id':fields.many2one('account.period','Period'),
        'converted':fields.boolean('Converted to Voucher'),
        }
dbf_details()

class dbf_file_get(osv.osv_memory):
    _name = "dbf.file.get"
    _description = "DBF File Fetcher"
    
    def getFiles(self, cr, uid, ids, context=None):
        user_loc = self.pool.get('res.users').read(cr, uid, uid,['location'])
        location = user_loc['location']
        for dbf_list in os.listdir(location):
            values={}
            if dbf_list.endswith('.dbf'):
                dbf_file_split = dbf_list.split('.')
                full_loc = location + '/' +dbf_list
                values={
                    'name':dbf_file_split[0],
                    'extension':'dbf',
                    'user_id':uid,
                    'full_location':full_loc,
                    }
                file_id = self.pool.get('dbf.files').search(cr, uid, [('name','ilike',dbf_file_split[0]),('full_location','ilike',full_loc)])
                if not file_id:
                    self.pool.get('dbf.files').create(cr, uid, values)
            elif dbf_list.endswith('.DBF'):
                dbf_file_split = dbf_list.split('.')
                full_loc = location + '/' +dbf_list
                values={
                    'name':dbf_file_split[0],
                    'extension':'DBF',
                    'user_id':uid,
                    'full_location':full_loc,
                    }
                file_id = self.pool.get('dbf.files').search(cr, uid, [('name','ilike',dbf_file_split[0]),('full_location','ilike',full_loc)])
                if not file_id:
                    self.pool.get('dbf.files').create(cr, uid, values)
        return {'type': 'ir.actions.act_window_close'}
dbf_file_get()
class dbf_reader(osv.osv_memory):
    def _get_files(self, cr, uid, context=None):
        netsvc.Logger().notifyChannel("res", netsvc.LOG_INFO, 'Nagprint')
        if context is None:
            context = {}
        dbffiles_obj = self.pool.get('dbf.files')
        netsvc.Logger().notifyChannel("User", netsvc.LOG_INFO, ' '+str(uid))
        res = dbffiles_obj.search(cr, uid, [('imported', '=', False),
                                            ('user_id', '=', uid)])
        #
        return res and res[0]
    _name = "dbf.reader"
    _description = "DBF Reader"
    _columns = {
        'fname':fields.function(_get_files, type='selection', method=True,string='Filename',store=True, readonly=False),
        #'filename': fields.many2one('dbf.files','Files for Conversion')
    }
    
    def convert(self, cr, uid, ids, context=None):
        user_pool = self.pool.get('res.users')
        for form in self.read(cr, uid, ids, context=context):
            if form['fname']:
                file_name = form['fname']
                netsvc.Logger().notifyChannel("file_name", netsvc.LOG_INFO, ' '+str(file_name))
                dbf_file_reader = self.pool.get('dbf.files').read(cr, uid, file_name,['name','extension','full_location'])
                user_read = self.pool.get('res.users').read(cr, uid, uid, ['location'])
                in_db = dbf.Dbf(dbf_file_reader['full_location'])
                new_csv = user_read['location'] + '/' + dbf_file_reader['name'] + '.csv'
                out_csv = csv.writer(open(new_csv,'wb'))
                names = []
                for field in in_db.header.fields:
                    names.append(field.name)
                out_csv.writerow(names)
                for rec in in_db:
                    out_csv.writerow(rec.fieldData)
                        
                in_db.close
                self.pool.get('dbf.files').write(cr, uid, file_name,{'converted_file':new_csv})
                '''
                for users in user_pool.browse(cr, uid, [user_id]):
                    user_name = users.name
                    location = users.location
                    location_filename = location + '/' + file_name + '.dbf'
                    new_csv = location + '/' + file_name + '.csv'
                    netsvc.Logger().notifyChannel("User", netsvc.LOG_INFO, ' '+str(user_name))
                    netsvc.Logger().notifyChannel("Location", netsvc.LOG_INFO, ' '+str(location))
                    netsvc.Logger().notifyChannel("Actual File", netsvc.LOG_INFO, ' '+str(location_filename))
                    in_db = dbf.Dbf(location_filename)
                    out_csv = csv.writer(open(new_csv,'wb'))
                    names = []
                    for field in in_db.header.fields:
                        names.append(field.name)
                    out_csv.writerow(names)
                    
                    for rec in in_db:
                        out_csv.writerow(rec.fieldData)
                        
                    in_db.close'''
        return True #{'type': 'ir.actions.act_window_close'}
    
    def dbfimport(self, cr, uid, ids, context=None):
        for form in self.read(cr, uid, ids, context=context):
            if form['filename']:
                file_name = form['filename']
                user_id = uid
                usr_reader = self.pool.get('res.users').read(cr, uid, user_id, ['location'])
                location = usr_reader['location']
                location_filename = location + '/' + file_name + '.csv'
                dbf_details =  csv.reader(open(location_filename,'rb'))
                for row in dbf_details:
                    if row[0]=='BATTYPECD':
                        #netsvc.Logger().notifyChannel("Row", netsvc.LOG_INFO, ' '+str(row))
                        continue
                    search_fields = [('battypecd','=',row[0]),
                                    ('batdt','=',row[1]),
                                    ('batltr','=',row[2]),
                                    ('docno','=',row[3]),
                                    ('amount','=',row[4]),
                                    ('trancd','=',row[5]),
                                    ('comm1','=',row[6]),
                                    ('comm2','=',row[7]),
                                    ('dcno','=',row[8]),
                                    ('filename','=',file_name),
                                     ]
                    
                    res_id = self.pool.get('dbf.details').search(cr, uid, search_fields)
                    if not res_id:
                        for period_search in self.pool.get('account.period').search(cr, uid, [('date_start','<=',row[1]),('date_stop','>=',row[1])]):
                            period_read = self.pool.get('account.period').read(cr, uid, period_search,['id'])
                            values= {
                                'battypecd':row[0],
                                'batdt':row[1],
                                'batltr':row[2],
                                'docno':row[3],
                                'amount':row[4],
                                'trancd':row[5],
                                'comm1':row[6],
                                'comm2':row[7],
                                'dcno':row[8],
                                'period_id':period_read['id'],
                                'filename':file_name,
                                }
                            self.pool.get('dbf.details').create(cr, uid, values)
        return True

dbf_reader()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

