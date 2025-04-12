# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date

class HrEmployeeChild(models.Model):
    _name = 'hr.employee.child'
    _description = "Employee's Child Information"
    _order = 'birth_date desc, name' # Sortera efter ålder

    name = fields.Char(string='Name', required=True)
    birth_date = fields.Date(string='Birth Date', required=True)
    # Överväg kryptering eller åtkomstkontroll för personnummer
    personnummer = fields.Char(string='Personal Identity Number')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    age = fields.Integer(string='Age', compute='_compute_age', store=True) # Lagra ålder för enklare sökning

    @api.depends('birth_date')
    def _compute_age(self):
        today = date.today()
        for child in self:
            if child.birth_date:
                # Använd Odoos fields.Date för säker konvertering
                born = child.birth_date
                child.age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            else:
                child.age = 0

    # TODO: Add constraint to validate personnummer format?