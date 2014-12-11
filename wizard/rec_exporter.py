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
import csv
import sys
import netsvc
import os

class export_ntm_class(osv.osv):
    _name = 'export.ntm.class'
    _description = 'Object Records Exporter'
    _columns = {
        'name':fields.many2one('ir.model','Model Name',domain=[('osv_memory','=',False)]),
        'encf_ids':fields.one2many('export.ntm.class.fields','export_id','Fields Inclusion'),
        }
    def get_fields(self,cr, uid, ids, context=None):
        self.onchange_object(cr, uid, ids)
        for model in self.read(cr, uid, ids, context=None):
            for model_fields in self.pool.get('ir.model.fields').search(cr, uid, [('model_id','=',model['name'][0])]):
                field_reader = self.pool.get('ir.model.fields').read(cr, uid, model_fields,context=None)
                values={
                    'export_id':model['id'],
                    'name':field_reader['id'],
                    'type':field_reader['ttype'],
                    'field_name':field_reader['name'],
                    'label':field_reader['field_description']
                    }
                self.pool.get('export.ntm.class.fields').create(cr, uid, values)
        return True
    
    def onchange_object(self, cr, uid, ids, context=None):
        for exporter in self.read(cr, uid, ids):
            exporter_id = exporter['id']
            field_list = self.pool.get('export.ntm.class.fields').search(cr, uid, [('export_id','=',exporter_id)])
            if not field_list:
                continue
            elif field_list:
                self.pool.get('export.ntm.class.fields').unlink(cr, uid, field_list)
        return True
    
    def write_to_csv(self,cr, uid, ids, context=None):
        for model in self.read(cr, uid, ids, context=None):
            model_read = self.pool.get('ir.model').read(cr, uid, model['name'][0],['model'])
            netsvc.Logger().notifyChannel("model_read", netsvc.LOG_INFO, ' '+str(model_read))
            model_name = model_read['model']
            netsvc.Logger().notifyChannel("model_name", netsvc.LOG_INFO, ' '+str(model_name))
            #model_name = "'"+model_name+"'"
            #netsvc.Logger().notifyChannel("model_name", netsvc.LOG_INFO, ' '+str(model_name))
            #search_model_record = "self.pool.get("+model_name+")"
            search_model_record = self.pool.get(model_name)
            netsvc.Logger().notifyChannel("test", netsvc.LOG_INFO, ' '+str(search_model_record))
            field_list = []
            field_names = []
            headers = []
            new_csv = "/home/netadmin/testeng/csv/"
            new_csv = new_csv + model['name'][1]+'.csv'
            out_csv = csv.writer(open(new_csv,'wb'))
            for fields in self.pool.get('export.ntm.class.fields').search(cr, uid, [('include_to_report','=',True),('export_id','=',model['id'])]):
                field_reader = self.pool.get('export.ntm.class.fields').read(cr, uid, fields, context=None)
                field_name = field_reader['field_name']
                field_list.append(field_name)
                field_label = field_reader['label']
                field_names.append(field_label)
            for fieldnames in field_names:
                headers.append(fieldnames)
            out_csv.writerow(headers)
            for records in search_model_record.search(cr, uid, [('id','!=','0')]):
                flusher = []
                netsvc.Logger().notifyChannel("flusher", netsvc.LOG_INFO, ' '+str(flusher))
                for field_reader in field_list:
                    field_lister=[field_reader]
                    details = search_model_record.read(cr, uid, records ,field_lister)
                    netsvc.Logger().notifyChannel("field_lister", netsvc.LOG_INFO, ' '+str(field_lister))
                    field_rec = details[field_reader]
                    flusher.append(field_rec)
                    netsvc.Logger().notifyChannel("field_rec", netsvc.LOG_INFO, ' '+str(field_rec))
                out_csv.writerow(flusher)
                netsvc.Logger().notifyChannel("flusher", netsvc.LOG_INFO, ' '+str(flusher))
        return True
    
export_ntm_class()

class export_ntm_class_fields(osv.osv):
    _name = 'export.ntm.class.fields'
    _description = 'Object Records Exporter - Fields'
    _columns = {
        'name':fields.many2one('ir.model.fields','Field Name'),
        'field_name':fields.char('Model ID',size=64),
        'label':fields.char('Label',size=64),
        'include_to_report':fields.boolean('Include to report?'),
        'export_id':fields.many2one('export.ntm.class','Export ID',ondelete='cascade'),
        'type':fields.char('Field Type',size=64),
        }
export_ntm_class_fields()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

