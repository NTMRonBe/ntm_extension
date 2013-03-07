import time
from osv import osv, fields, orm
import netsvc
import pooler
from tools.translate import _

class ob_import(osv.osv):
    _name = 'ob.import'
    _description = "Import Opening Balance Entries"
    _columns = {
        'name':fields.char('Name',size=64),
        'journal_id':fields.many2one('account.journal','Journal'),
        'ref':fields.char('Reference',size=64),
        'period_id':fields.many2one('account.period','Period'),
        'account_id':fields.many2one('account.account','Account'),
        'analytic_id':fields.many2one('account.analytic.account','Analytic Account'),
        'debit':fields.float('Debit'),
        'credit':fields.float('Credit'),
        'currency_id':fields.many2one('res.currency','Currency',help="Currency of the amount"),
        'date':fields.date('Effective Date'),
        'partner_id':fields.many2one('res.partner','Partner'),
        'imported':fields.boolean('Imported'),
        }
ob_import()

class ob_import_wiz(osv.osv_memory):
    _name = 'ob.import.wiz'
    
    def import_wiz(self, cr, uid, ids, context=None):
        aml_pool = self.pool.get('account.move.line')
        am_pool = self.pool.get('account.move')
        obi = self.pool.get('ob.import')
        for obi_lines in obi.search(cr, uid, [('imported','=',False)]):
            obi_fields = ['name','journal_id','ref','period_id','account_id','analytic_id',
                          'debit','credit','currency_id','date','partner_id']
            obi_read = obi.read(cr, uid, obi_lines,obi_fields)
            am_check = am_pool.search(cr, uid,[('ref','=',obi_read['ref'])])
            if not am_check:
                move = {
                    'ref':obi_read['ref'],
                    'journal_id':obi_read['journal_id'][0],
                    'period_id':obi_read['period_id'][0],
                    'date':obi_read['date'],
                    'state':'draft',
                }
                move_id = am_pool.create(cr, uid, move)
                move_line = {
                    'name':obi_read['name'],
                    'ref':obi_read['ref'],
                    #'partner_id':obi_read['partner_id'][0],
                    'journal_id':obi_read['journal_id'][0],
                    'period_id':obi_read['period_id'][0],
                    'account_id':obi_read['account_id'][0],
                    #'analytic_account_id':obi_read['analytic_id'][0],
                    'debit':obi_read['debit'],
                    'credit':obi_read['credit'],
                    'date':obi_read['date'],
                    'move_id':move_id,
                }
                aml_pool.create(cr, uid, move_line)
            elif am_check:
                for aml in am_check:
                    am_read = am_pool.read(cr, uid, aml, ['id'])
                    move_line = {
                        'name':obi_read['name'],
                        'ref':obi_read['ref'],
                        #'partner_id':obi_read['partner_id'][0],
                        'journal_id':obi_read['journal_id'][0],
                        'period_id':obi_read['period_id'][0],
                        'account_id':obi_read['account_id'][0],
                        #'analytic_account_id':obi_read['analytic_id'][0],
                        'debit':obi_read['debit'],
                        'credit':obi_read['credit'],
                        'date':obi_read['date'],
                        'move_id':am_read['id'],
                    }
                    aml_pool.create(cr, uid, move_line)
        return {'type': 'ir.actions.act_window_close'}
ob_import_wiz()