import time
from osv import osv, fields, orm
import netsvc
import pooler
import psycopg2
from tools.translate import _
import decimal_precision as dp

class fund_transfer(osv.osv):
    _name = 'fund.transfer'
    _description = "Fund Transfers"
    _columns = {
        'name':fields.char('Transfer ID',size=64),
        'type':fields.selection([
                                 ('b2b','Bank to Bank'),
                                 ('a2a','Analytic to Analytic')
                                 ],'Type'),
        'period_id':fields.many2one('account.period','Period'),
        'journal_id':fields.many2one('account.journal','Journal'),
        'src_account':fields.many2one('account.account','Source Account'),
        'dest_account':fields.many2one('account.account','Destination Account'),
        'src_analytic_account':fields.many2one('account.analytic.account','Source Analytic Account'),
        'dest_analytic_account':fields.many2one('account.analytic.account','Destination Analytic Account'),
        }
fund_transfer()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:,