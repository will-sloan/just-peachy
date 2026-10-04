"""Lossless current-data grouping checks. README_PRODUCTION_SCOPE.md."""
import unittest
import discover_production_backup_action_v2 as discovery
from test_production_scope import ScopeTests


class GroupingTests(unittest.TestCase):
    setUp=ScopeTests.setUp

    def test_hundred_direct_data_children_group_without_omission(self):
        for index in range(100):(self.base/'data'/('current-%03d.json'%index)).write_text('{}')
        value=discovery.discover(self.base,self.campaign,self.home)
        sources={row['source'] for row in value['roots']};members={row['path'] for row in value['members']}
        self.assertIn(str(self.base/'data'),sources);self.assertIn(str(self.base/'config'),sources)
        self.assertNotIn(str(self.base/'data/settings.json'),sources)
        self.assertLessEqual(len(sources),64)
        for index in range(100):self.assertIn(str(self.base/'data'/('current-%03d.json'%index)),members)
        self.assertIn(str(self.base/'config/calibration.json'),members)
        self.assertIn(str(self.campaign/'field-operator-sessions-v10115/audio'),members)

    def test_still_oversized_roots_return_complete_diagnostic_membership(self):
        for index in range(65):(self.campaign/('field-operator-sessions-v%d'%(12000+index))).mkdir()
        value=discovery.discover(self.base,self.campaign,self.home)
        self.assertEqual(value['status'],'COMPLETE_ROOT_LIST_NEEDS_GROUPING_REVIEW')
        self.assertTrue(value['issues']);self.assertGreater(value['observed_root_count'],64)
        names={row['source'] for row in value['roots']}
        for index in range(65):self.assertIn(str(self.campaign/('field-operator-sessions-v%d'%(12000+index))),names)
        self.assertNotIn('members',value)


if __name__=='__main__':unittest.main()
