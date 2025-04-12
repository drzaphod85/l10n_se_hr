from odoo import models, fields, api
from datetime import datetime, date
import math

class HrPayslipInherit(models.Model):
    _inherit = 'hr.payslip'

    tax_table_type = fields.Selection([
        ('table_29', 'Table 29 - Monthly salary'),
        ('table_30', 'Table 30 - Weekly salary'),
        ('table_31', 'Table 31 - Daily salary')
    ], string='Tax Table Type', default='table_29')

    tax_column = fields.Selection([
        ('column_1', 'Column 1 - No deductions'),
        ('column_2', 'Column 2 - 30% tax reduction'),
        ('column_3', 'Column 3 - Pension deduction'),
        ('column_4', 'Column 4 - Pension and 30% tax reduction'),
        ('column_5', 'Column 5 - Sea income'),
        ('column_6', 'Column 6 - Sea income with deduction')
    ], string='Tax Column', default='column_1')
    
    church_tax_applied = fields.Boolean(string='Church Tax Applied', compute='_compute_church_tax_applied')
    tax_table_number = fields.Char(related='employee_id.tax_table_number', string='Tax Table Number', readonly=True)
    
    @api.depends('employee_id')
    def _compute_church_tax_applied(self):
        for payslip in self:
            payslip.church_tax_applied = payslip.employee_id.church_member

    def action_compute_tax(self):
        for payslip in self:
            # Get tax rates from municipality
            total_tax_rate = payslip.employee_id.municipality_id.total_tax_rate / 100.0
            church_tax_rate = 0.0
            if payslip.church_tax_applied:
                church_tax_rate = payslip.employee_id.municipality_id.church_tax_rate / 100.0
            
            # Calculate taxes for each line
            for line in payslip.line_ids.filtered(lambda l: l.category_id.code == 'GROSS'):
                taxable_amount = line.amount
                
                # Basic tax calculation
                tax_amount = taxable_amount * total_tax_rate
                
                # Add church tax if applicable
                if payslip.church_tax_applied:
                    church_tax = taxable_amount * church_tax_rate
                    tax_amount += church_tax
                
                # Find or create tax line
                tax_line = payslip.line_ids.filtered(lambda l: l.code == 'TAX')
                if tax_line:
                    tax_line.amount = tax_amount
                else:
                    # This would need the appropriate salary rule to be configured
                    pass
                    
                # Calculate net amount
                net_line = payslip.line_ids.filtered(lambda l: l.code == 'NET')
                if net_line:
                    net_line.amount = taxable_amount - tax_amount