"""Provenance rejection tests. README_INTEGRATED_PREFIX_REUSE.md."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from common import bind,freeze
from integrated_prefix_reuse import STATUS,cap_only_sources,load_reuse,reuse_cell,validate_join,validate_reused


class PrefixTests(unittest.TestCase):
    def plans(self):
        rows=[dict(cell_id=str(i),job_id='job',contract={'mode':'open'},parents=['parent'],cache_key='old') for i in range(3)]
        old=dict(scope='main',required=3,jobs=['job'],rows=rows,context=dict(code=['old'],qualification=['old'],source='fixed',roster='fixed'))
        new=deepcopy(old);new['context'].update(code=['new'],qualification=['new'],reuse_review='receipt')
        for row in new['rows']:row['cache_key']='new'
        receipt=dict(status=STATUS,completed=2,cells=[dict(path='a'),dict(path='b')])
        return new,old,receipt

    def test_new_code_and_cache_keep_same_full_population(self):
        validate_join(*self.plans())

    def test_source_roster_and_unknown_context_changes_rejected(self):
        for key,value in [('source','changed'),('roster','changed'),('other','new')]:
            new,old,receipt=self.plans();new['context'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_join(new,old,receipt)

    def test_parent_contract_identity_order_or_population_changes_rejected(self):
        for change in ('parent','contract','identity','order','job','scope','required'):
            new,old,receipt=self.plans()
            if change=='parent':new['rows'][0]['parents']=['wrong']
            elif change=='contract':new['rows'][0]['contract']['mode']='closed'
            elif change=='identity':new['rows'][0]['cell_id']='foreign'
            elif change=='order':new['rows'].reverse()
            elif change=='job':new['jobs']=['foreign']
            elif change=='scope':new['scope']='panel'
            elif change=='required':new['required']=2
            with self.subTest(change=change),self.assertRaises(ValueError):validate_join(new,old,receipt)

    def test_unreviewed_missing_duplicate_and_false_complete_prefix_rejected(self):
        for change in ('status','missing','duplicate','complete','empty'):
            new,old,receipt=self.plans()
            if change=='status':receipt['status']='READY_FOR_REVIEW'
            elif change=='missing':receipt['cells'].pop()
            elif change=='duplicate':receipt['cells'][1]=receipt['cells'][0]
            elif change=='complete':receipt['completed']=3;receipt['cells'].append(dict(path='c'))
            elif change=='empty':receipt['completed']=0;receipt['cells']=[]
            with self.subTest(change=change),self.assertRaises(ValueError):validate_join(new,old,receipt)

    def test_only_declared_caps_change_in_producer_source(self):
        self.assertEqual(len(cap_only_sources()),6)

    def test_reuse_preserves_original_payload_and_producer_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);freeze(root/'plan.json',{'old':True});freeze(root/'new-plan.json',{'new':True})
            old_plan,new_plan=bind(root/'plan.json'),bind(root/'new-plan.json')
            old=dict(cell_id='cell',job_id='job',parents=[],contract={'mode':'open'},plan=old_plan,cache_key='old',outputs={'unchanged':'payload'})
            freeze(root/'cell.json',old);b=bind(root/'cell.json');receipt=dict(completed=1,cells=[b],plan=old_plan)
            row=dict(old,cache_key='new');result=reuse_cell(row,new_plan,receipt,0)
            self.assertEqual(result['outputs'],old['outputs']);self.assertEqual(result['reused_from'],b)
            self.assertEqual(result['cache_key'],'new');self.assertEqual(result['plan'],new_plan)
            validate_reused(result,row,new_plan,receipt,0)
            for key,value in [('outputs',{}),('reused_from',{}),('cache_key','old'),('execution_source','generated')]:
                bad=deepcopy(result);bad[key]=value
                with self.subTest(key=key),self.assertRaises(ValueError):validate_reused(bad,row,new_plan,receipt,0)
            with self.assertRaises(ValueError):reuse_cell(row,new_plan,receipt,1)
            with self.assertRaises(ValueError):reuse_cell(dict(row,parents=['foreign']),new_plan,receipt,0)

    def test_foreign_review_is_rejected_before_it_is_loaded(self):
        with patch('integrated_prefix_reuse.load',return_value={'private_prefix_review':'qualified'}), \
                patch('integrated_prefix_reuse.verify') as verify:
            with self.assertRaises(ValueError):load_reuse({'context':{'reuse_review':'foreign'}})
            verify.assert_not_called()


if __name__=='__main__':unittest.main()
