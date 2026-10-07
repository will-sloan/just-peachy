"""Finite interactive history actions, never automatic; README_FIELD_OPERATOR_QUALIFICATION_V4.md."""
from pathlib import Path
from field_transfer_v2 import verify_zip,sha

class Actions:
    LIMITS={'save':1,'open':16,'export':1,'delete':1,'import':1}
    def __init__(self,root,outputs,derived):
        self.root=Path(root);self.outputs=outputs;self.derived=derived
        self.counts={key:0 for key in self.LIMITS};self.completed=[]
        self.binding=None;self.deleted=False;self.imported=False
        self.destination=self.root/'conversation_exports/transfer.zip'

    def check(self,controller,action,values):
        if action not in self.LIMITS or type(values) is not dict:
            raise ValueError('Action unavailable in this recording process')
        if self.outputs.stop_event.is_set() or controller._archive_failure is not None:
            raise RuntimeError('First failure remains latched until process close')
        if self.counts[action]>=self.LIMITS[action]:
            raise ValueError('Action allowance exhausted; Return closes this process')
        controller._ensure_no_enrollment()
        if controller.engine is not None or controller.archive is not None or controller.playback is not None:
            raise ValueError('Stop recording and wait for closure before history actions')
        identifier=controller.session_store.delivery_identifier
        if identifier is None or not controller.session_store.delivery_epoch:
            raise ValueError('Complete this process recording first')
        expected={'save':dict(identifier=identifier),'open':dict(identifier=identifier),
                  'export':dict(identifier=identifier,path=str(self.destination),audio=True,consent=True),
                  'delete':dict(identifier=identifier,confirmed=True),
                  'import':dict(path=str(self.destination),consent=True)}
        if values!=expected[action]:raise ValueError('Action identity, consent or admitted path changed')
        if action in ('save','export') and self.deleted:raise ValueError('Original recording already deleted')
        if action=='save' and self.binding is not None:raise ValueError('Exported metadata is frozen')
        if action=='export':
            doc=controller.session_store.metadata(identifier)
            if doc.get('state')!='SAVED' or doc.get('pinned') is not True:
                raise ValueError('Save this recording before exporting')
        if action=='delete' and (self.binding is None or self.deleted):
            raise ValueError('Verified full export is required before deletion')
        if action=='import' and (not self.deleted or self.imported):
            raise ValueError('This import restores the exported recording into its absent ID')
        if action=='open' and self.deleted and not self.imported:
            raise ValueError('Import this recording before reopening it')
        return identifier

    def run(self,controller,action,values,perform):
        identifier=self.check(controller,action,values)
        self.counts[action]+=1
        try:
            folder=controller.session_store.folder(identifier)
            if action=='delete':
                with self.outputs.physical_files.allow_copied_delete(folder,self.binding,self.destination):
                    result=perform(action,values)
                self.deleted=True
            else:
                result=perform(action,values)
            if action=='export':
                self.binding=verify_zip(self.derived,self.destination,folder,identifier)
            if action=='import':
                checked={name:dict(bytes=(folder/name).stat().st_size,sha256=sha(folder/name))
                         for name in self.binding['files']}
                if checked!=self.binding['files']:raise RuntimeError('Imported payload changed')
                self.imported=True
            self.completed.append(dict(action=action,complete=True))
            return result
        except BaseException as exc:
            self.outputs.fail('entry',exc,lambda:controller.request_archive_stop('OPERATOR_ACTION: '+str(exc)))
            raise
