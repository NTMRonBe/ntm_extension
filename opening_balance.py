import time
from osv import osv, fields, orm
import netsvc
import pooler
from tools.translate import _
import re

import calendar
import copy
import datetime
import logging
import warnings
import operator
import pickle
import re
import time
import traceback
import types

from lxml import etree
from tools.config import config

import tools
from tools.safe_eval import safe_eval as eval

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
        'currency_id':fields.related('account_id','currency_id',type='many2one',relation='res.currency',store=True, string='Posting Currency'),
        'date':fields.date('Effective Date'),
        'partner_id':fields.many2one('res.partner','Partner'),
        'imported':fields.boolean('Imported'),
        }
    
    def import_data(self, cr, uid, fields, datas, mode='init', current_module='', noupdate=False, context=None, filename=None):
        """
        Import given data in given module

        :param cr: database cursor
        :param uid: current user id
        :param fields: list of fields
        :param data: data to import
        :param mode: 'init' or 'update' for record creation
        :param current_module: module name
        :param noupdate: flag for record creation
        :param context: context arguments, like lang, time zone,
        :param filename: optional file to store partial import state for recovery
        :rtype: tuple

        This method is used when importing data via client menu.

        Example of fields to import for a sale.order::

            .id,                         (=database_id)
            partner_id,                  (=name_search)
            order_line/.id,              (=database_id)
            order_line/name,
            order_line/product_id/id,    (=xml id)
            order_line/price_unit,
            order_line/product_uom_qty,
            order_line/product_uom/id    (=xml_id)
        """
        if not context:
            context = {}
        def _replace_field(x):
            x = re.sub('([a-z0-9A-Z_])\\.id$', '\\1/.id', x)
            return x.replace(':id','/id').split('/')
        fields = map(_replace_field, fields)
        logger = netsvc.Logger()
        ir_model_data_obj = self.pool.get('ir.model.data')

        # mode: id (XML id) or .id (database id) or False for name_get
        def _get_id(model_name, id, current_module=False, mode='id'):
            if mode=='.id':
                id = int(id)
                obj_model = self.pool.get(model_name)
                dom = [('id', '=', id)]
                if obj_model._columns.get('active'):
                    dom.append(('active', 'in', ['True','False']))
                ids = obj_model.search(cr, uid, dom, context=context)
                if not len(ids):
                    raise Exception(_("Database ID doesn't exist: %s : %s") %(model_name, id))
            elif mode=='id':
                if '.' in id:
                    module, xml_id = id.rsplit('.', 1)
                else:
                    module, xml_id = current_module, id
                record_id = ir_model_data_obj._get_id(cr, uid, module, xml_id)
                ir_model_data = ir_model_data_obj.read(cr, uid, [record_id], ['res_id'], context=context)
                if not ir_model_data:
                    raise ValueError('No references to %s.%s' % (module, xml_id))
                id = ir_model_data[0]['res_id']
            else:
                obj_model = self.pool.get(model_name)
                ids = obj_model.name_search(cr, uid, id, operator='ilike', context=context)
                if not ids:
                    raise ValueError('No record found for %s' % (id,))
                id = ids[0][0]
            return id

        # IN:
        #   datas: a list of records, each record is defined by a list of values
        #   prefix: a list of prefix fields ['line_ids']
        #   position: the line to process, skip is False if it's the first line of the current record
        # OUT:
        #   (res, position, warning, res_id) with
        #     res: the record for the next line to process (including it's one2many)
        #     position: the new position for the next line
        #     res_id: the ID of the record if it's a modification
        def process_liness(self, datas, prefix, current_module, model_name, fields_def, position=0, skip=0):
            line = datas[position]
            row = {}
            warning = []
            data_res_id = False
            xml_id = False
            nbrmax = position+1

            done = {}
            for i in range(len(fields)):
                res = False
                if i >= len(line):
                    raise Exception(_('Please check that all your lines have %d columns.') % (len(fields),))

                field = fields[i]
                if field[:len(prefix)] <> prefix:
                    if line[i] and skip:
                        return False
                    continue

                # ID of the record using a XML ID
                if field[len(prefix)]=='id':
                    try:
                        data_res_id = _get_id(model_name, line[i], current_module, 'id')
                    except ValueError, e:
                        pass
                    xml_id = line[i]
                    continue

                # ID of the record using a database ID
                elif field[len(prefix)]=='.id':
                    data_res_id = _get_id(model_name, line[i], current_module, '.id')
                    continue

                # recursive call for getting children and returning [(0,0,{})] or [(1,ID,{})]
                if fields_def[field[len(prefix)]]['type']=='one2many':
                    if field[len(prefix)] in done:
                        continue
                    done[field[len(prefix)]] = True
                    relation_obj = self.pool.get(fields_def[field[len(prefix)]]['relation'])
                    newfd = relation_obj.fields_get(cr, uid, context=context)
                    pos = position
                    res = []
                    first = 0
                    while pos < len(datas):
                        res2 = process_liness(self, datas, prefix + [field[len(prefix)]], current_module, relation_obj._name, newfd, pos, first)
                        if not res2:
                            break
                        (newrow, pos, w2, data_res_id2, xml_id2) = res2
                        nbrmax = max(nbrmax, pos)
                        warning += w2
                        first += 1
                        if (not newrow) or not reduce(lambda x, y: x or y, newrow.values(), 0):
                            break
                        res.append( (data_res_id2 and 1 or 0, data_res_id2 or 0, newrow) )

                elif fields_def[field[len(prefix)]]['type']=='many2one':
                    relation = fields_def[field[len(prefix)]]['relation']
                    if len(field) == len(prefix)+1:
                        mode = False
                    else:
                        mode = field[len(prefix)+1]
                    res = line[i] and _get_id(relation, line[i], current_module, mode) or False

                elif fields_def[field[len(prefix)]]['type']=='many2many':
                    relation = fields_def[field[len(prefix)]]['relation']
                    if len(field) == len(prefix)+1:
                        mode = False
                    else:
                        mode = field[len(prefix)+1]

                    # TODO: improve this by using csv.csv_reader
                    res = []
                    if line[i]:
                        for db_id in line[i].split(config.get('csv_internal_sep')):
                            res.append( _get_id(relation, db_id, current_module, mode) )
                    res = [(6,0,res)]

                elif fields_def[field[len(prefix)]]['type'] == 'integer':
                    res = line[i] and int(line[i]) or 0
                elif fields_def[field[len(prefix)]]['type'] == 'boolean':
                    res = line[i].lower() not in ('0', 'false', 'off')
                elif fields_def[field[len(prefix)]]['type'] == 'float':
                    res = line[i] and float(line[i]) or 0.0
                elif fields_def[field[len(prefix)]]['type'] == 'selection':
                    for key, val in fields_def[field[len(prefix)]]['selection']:
                        if line[i] in [tools.ustr(key), tools.ustr(val)]:
                            res = key
                            break
                    if line[i] and not res:
                        logger.notifyChannel("import", netsvc.LOG_WARNING,
                                _("key '%s' not found in selection field '%s'") % \
                                        (line[i], field[len(prefix)]))
                        warning += [_("Key/value '%s' not found in selection field '%s'") % (line[i], field[len(prefix)])]
                else:
                    res = line[i]

                row[field[len(prefix)]] = res or False

            result = (row, nbrmax, warning, data_res_id, xml_id)
            return result

        fields_def = self.fields_get(cr, uid, context=context)

        if config.get('import_partial', False) and filename:
            data = pickle.load(file(config.get('import_partial')))
            original_value = data.get(filename, 0)

        position = 0
        while position<len(datas):
            res = {}

            (res, position, warning, res_id, xml_id) = \
                    process_liness(self, datas, [], current_module, self._name, fields_def, position=position)
            if len(warning):
                cr.rollback()
                return (-1, res, 'Line ' + str(position) +' : ' + '!\n'.join(warning), '')

            try:
                id = ir_model_data_obj._update(cr, uid, self._name,
                     current_module, res, mode=mode, xml_id=xml_id,
                     noupdate=noupdate, res_id=res_id, context=context)
            except Exception, e:
                return (-1, res, 'Line ' + str(position) +' : ' + tools.ustr(e), '')

            if config.get('import_partial', False) and filename and (not (position%100)):
                data = pickle.load(file(config.get('import_partial')))
                data[filename] = position
                pickle.dump(data, file(config.get('import_partial'), 'wb'))
                if context.get('defer_parent_store_computation'):
                    self._parent_store_compute(cr)
                cr.commit()

        if context.get('defer_parent_store_computation'):
            self._parent_store_compute(cr)
        return (position, 0, 0, 0)
ob_import()

class ob_import_wiz(osv.osv_memory):
    _name = 'ob.import.wiz'
        
    def import_wiz(self, cr, uid, ids, context=None):
        aml_pool = self.pool.get('account.move.line')
        am_pool = self.pool.get('account.move')
        obi = self.pool.get('ob.import')
        for obi_lines in obi.search(cr, uid, [('imported','=',False)]):
            obi_fields = ['name','journal_id','ref','period_id','currency_id','account_id','analytic_id',
                          'debit','credit','currency_id','date','partner_id']
            obi_read = obi.read(cr, uid, obi_lines,obi_fields)
            am_check = am_pool.search(cr, uid,[('ref','=',obi_read['ref'])])
            partner_id= False
            analytic_id= False
            curr_id = False
            if obi_read['partner_id']:
                 partner_id=obi_read['partner_id'][0]
            if obi_read['analytic_id']:
                analytic_id=obi_read['analytic_id'][0]
            if obi_read['currency_id']:
                curr_id=obi_read['currency_id'][0]
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
                    'partner_id':partner_id,
                    'journal_id':obi_read['journal_id'][0],
                    'period_id':obi_read['period_id'][0],
                    'account_id':obi_read['account_id'][0],
                    'currency_id':curr_id,
                    'analytic_account_id':analytic_id,
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
                        'partner_id':partner_id,
                        'currency_id':curr_id,
                        'journal_id':obi_read['journal_id'][0],
                        'period_id':obi_read['period_id'][0],
                        'account_id':obi_read['account_id'][0],
                        'analytic_account_id':analytic_id,
                        'debit':obi_read['debit'],
                        'credit':obi_read['credit'],
                        'date':obi_read['date'],
                        'move_id':am_read['id'],
                    }
                    aml_pool.create(cr, uid, move_line)
            obi.write(cr, uid,obi_lines,{'imported':True})
        return {'type': 'ir.actions.act_window_close'}
ob_import_wiz()