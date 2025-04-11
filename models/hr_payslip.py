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


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'
    
    is_swedish_specific = fields.Boolean(string='Swedish Specific Rule')
    applies_church_tax = fields.Boolean(string='Applies Church Tax')


class SwedishTaxTable(models.Model):
    _name = 'hr.swedish.tax.table'
    _description = 'Swedish Tax Table'
    
    name = fields.Char(string='Name', required=True)
    table_number = fields.Char(string='Table Number', required=True)
    year = fields.Integer(string='Year', required=True, default=lambda self: fields.Date.today().year)
    table_type = fields.Selection([
        ('table_29', 'Table 29 - Monthly salary'),
        ('table_30', 'Table 30 - Weekly salary'),
        ('table_31', 'Table 31 - Daily salary')
    ], string='Table Type', required=True)
    column_ids = fields.One2many('hr.swedish.tax.table.column', 'table_id', string='Columns')
    
    _sql_constraints = [
        ('table_year_unique', 'unique(table_number, year)', 'Tax table must be unique per year.')
    ]
    
    @api.model
    def import_tax_tables(self):
        """Import tax tables from Skatteverket"""
        # This would fetch and parse tax tables from Skatteverket
        # Implementation depends on available APIs or files
        pass


class SwedishTaxTableColumn(models.Model):
    _name = 'hr.swedish.tax.table.column'
    _description = 'Swedish Tax Table Column'
    
    name = fields.Char(string='Name', required=True)
    column_number = fields.Integer(string='Column Number', required=True)
    table_id = fields.Many2one('hr.swedish.tax.table', string='Tax Table', required=True, ondelete='cascade')
    bracket_ids = fields.One2many('hr.swedish.tax.bracket', 'column_id', string='Tax Brackets')


class SwedishTaxBracket(models.Model):
    _name = 'hr.swedish.tax.bracket'
    _description = 'Swedish Tax Bracket'
    _order = 'lower_limit'
    
    column_id = fields.Many2one('hr.swedish.tax.table.column', string='Table Column', required=True, ondelete='cascade')
    lower_limit = fields.Float(string='Lower Income Limit', required=True)
    upper_limit = fields.Float(string='Upper Income Limit', required=True)
    tax_amount = fields.Float(string='Tax Amount', required=True, help='Fixed amount or percentage depending on table type')
    is_percentage = fields.Boolean(string='Is Percentage', default=False)
    
    @api.constrains('lower_limit', 'upper_limit')
    def _check_limits(self):
        for bracket in self:
            if bracket.lower_limit >= bracket.upper_limit:
                raise ValidationError("Upper limit must be greater than lower limit.")