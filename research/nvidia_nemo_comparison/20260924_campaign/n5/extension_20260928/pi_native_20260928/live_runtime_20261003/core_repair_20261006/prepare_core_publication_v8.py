"""Prepare one unapproved final build35 source plan; README_CORE_PUBLICATION_V8.md."""
import ctypes
_k=ctypes.WinDLL('kernel32',use_last_error=True)
_k.GetCurrentProcess.restype=ctypes.c_void_p
_h=_k.GetCurrentProcess()
_k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
if not _k.SetProcessAffinityMask(_h,16384):raise ctypes.WinError(ctypes.get_last_error())
import argparse,hashlib,json,os,re,shutil,stat,time,uuid
from pathlib import Path,PurePosixPath
ROOT=Path('G:/Just_Peachy_N1/20260924_campaign/worktree')
HERE=Path(__file__).parent
Q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BASE=Q/'audit-preparation/final-build28-reviewed-plan-c30ef5c38a5d4752ae0eb6a0fcdd4d19/REVIEWED_PLAN.json'
BASE_SHA='0639e6249fb288120657e9e1fffee56d6b72f7e9c452f4faaf071c20df035d6f'
PIN='4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767'
SOURCE_REVIEW=Q/'audit-preparation/caption-package31-f6383c985d4d41e6b065ff9487dd19ad/SOURCE_DIFF_REVIEW.json'
SOURCE_REVIEW_SHA='6894adf19266061a15a71dc103d7317303652d68d58a4e27b74016430caaf4ca'
MIDDLE_SOURCE_REVIEW=Q/'audit-preparation/sidecar-package30-98954655204a43a99b28375e33d3faf6/SOURCE_DIFF_REVIEW.json'
MIDDLE_SOURCE_REVIEW_SHA='337cfff9ac688ee947b66e2920306dbca5c11a72fd230486ad35eec54bfd34c7'
PARENT_SOURCE_REVIEW=Q/'audit-preparation/core-package-v1-98d8679173344e6cb1f97599f489a1b7/SOURCE_DIFF_REVIEW.json'
PARENT_SOURCE_REVIEW_SHA='2f2b7b92fe54c87c5f1713c3cffc2f97420b1fc5d3f7f86566c043348d01549c'
PARENT_PIN='b2eeab82452d5b87515477c4a562ce167cf6d35503a16df6a4febc1b1af25569'
PACKAGE=Q/'audit-preparation/caption-package31-f6383c985d4d41e6b065ff9487dd19ad/package'
PACKAGE_CONTENT_SHA='f65029c4d476fd557e073890dacaec218c0c2a6ce877c93a466c50a04e272b8d'
REPLACEMENT_ROOT=HERE/'caption_snapshot_20261006'
MIDDLE_REPLACEMENT_ROOT=HERE/'sqlite_sidecar_race_20261006'
PARENT_PROPOSER_SHA='46f580f1521eba1bab0117ba0f4766a51b0e6c319d64f8c8391a406a6d8f0b5d'
PARENT_REVIEWER_SHA='2ea65d63bd269f51f3ee7a65332e6e647258aade77b5cd03fcc3bd3bd5d49037'
PARENT_README_SHA='ed2220c82a92cb893ae0362c70d3675aa99f2f7a76bbe73408a77f4adc33166e'
FINAL_BUILDER=HERE.parent.parent/'runtime_handoff_tools/build_handoff_v2.py'
FINAL_BUILDER_SHA='34bd6696f360dd0c50a0e1817fc328b1d5a7983aa968d391c264fb8263349c6f'
C='research/nvidia_nemo_comparison/20260924_campaign/n5/completion_20261001/'
L='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/'
TRACKED=('DELIVERY_START_HERE.md',C+'ACCEPTANCE.json',C+'ACCEPTANCE_SCOPE.md',
    C+'BACKEND_COMBINATIONS.md',C+'CURRENT_RUNTIME_PROGRESS.md',C+'INSTALL_HEALTH_AND_RECOVERY.md',
    C+'MODE_GUIDE.md',C+'PATHS_AND_BACKUPS.md',C+'START_HERE_CURRENT.md',
    C+'FINAL_OPERATOR_GUIDE.md',C+'CHATGPT_HANDOFF.md',L+'MODE_GUIDE.md',
    L+'README_PIPELINES.md',L+'CORE_REPAIR_PIPELINE_NOTES.md',L+'CORE_REPAIR_TECHNICAL_NOTES.md',
    L+'pipelines/chunk52_threads2.md',L+'pipelines/command_matrix.md',
    L+'pipelines/current_delayed.md',L+'pipelines/pyannote_redimnet.md',L+'pipelines/pyannote_titanet.md')
SELECTED='''activate_core_desktop_action29.py application_controller.py asr_segment_contract.py asr_segment_runtime.py build_core_package_v1.py CAPTION_AUDIT.md caption_paragraphs.py check_asr_segments.py check_caption_repair.py classic_frontend.py core_database_recovery.py CORE_REPAIR_TECHNICAL_NOTES.md d1_spatial_policy.py gallery_snapshot_io.py host_core_operations_v2.py host_core_operations_v3.py host_core_operations_v4.py host_core_operations_v5.py host_core_operations.py host_inspect_core.py identity_modes.py inspect_core_storage.py installed_engine.py launch_core_full_app_hour.py launcher.py mature_frontend.py native_core_live_check_v2.py native_core_live_check.py native_core_saved_check_v2.py native_core_saved_check.py native_scope.py personal_gallery.py prepare_core_activation29.py prepare_core_database_recovery_v2.py prepare_core_endurance.py prepare_core_native_validation_v2.py prepare_core_native_validation.py prepare_core_publication_v1.py prepare_core_stage29_v2.py prepare_core_stage29.py README_ASR_SEGMENTS.md README_CAPTION_REPAIR.md README_CORE_ACTIVATION29.md README_CORE_BACKUP_V2.md README_CORE_BACKUP.md README_CORE_ENDURANCE.md README_CORE_INSPECTION.md README_CORE_NATIVE_VALIDATION_V2.md README_CORE_NATIVE_VALIDATION.md README_CORE_OPERATIONS_V3.md README_CORE_OPERATIONS_V4.md README_CORE_OPERATIONS_V5.md README_CORE_OPERATIONS.md README_CORE_PACKAGE_V1.md README_CORE_PUBLICATION.md README_CORE_REPAIR.md README_CORE_STAGE_V2.md README_CORE_STAGE.md README_DATABASE_RECOVERY_V2.md README_DATABASE_RECOVERY.md README_GALLERY_CAPACITY.md README_IDENTITY_MODES.md README_RUNTIME_CAPACITY.md README_STORAGE_RECOVERY.md reconcile_core_backup_v2.py reconcile_core_backup.py recover_core_database_copy.py recover_core_database_v2.py recover_core_database.py review_core_publication_v1.py run_host_caption_checks.py run_host_identity_checks.py run_host_storage_checks.py runtime_support.py stage_c24_endurance_input.py storage_support.py storage.py test_gallery_capacity.py test_identity_modes.py test_identity_pinned.py test_installed_caption_projection.py test_runtime_capacity.py test_storage_recovery.py worker.py'''.split()
CROSS_SOURCES=('ui_restore_20261004/xvf_readiness.py',
    'ui_restore_20261004/xvf_readiness_helper.py')
SELECTED += '''activate_core_desktop_action30.py prepare_core_activation30.py prepare_core_native_validation_v3.py prepare_core_endurance30.py launch_core_full_app_hour30.py stage_c24_endurance_input30.py review_core_full_app_hour.py review_core_full_app_hour30.py README_CORE_BUILD30_HELPERS.md README_CORE_HOUR_REVIEW.md host_core_operations_v6.py README_CORE_OPERATIONS_V6.md inspect_sqlite_guard_failure.py README_SQLITE_GUARD_INSPECTION.md prepare_core_publication_v2.py review_core_publication_v2.py README_CORE_PUBLICATION_V2.md'''.split()
SELECTED += ['host_core_operations_v7.py','README_CORE_OPERATIONS_V7.md']
SELECTED += ['host_core_operations_v8.py','README_CORE_OPERATIONS_V8.md','README_CORE_HOUR_DISPATCH.md']
SELECTED += ['review_hour01_lanes.py','README_HOUR01_LANES.md',
    'host_core_operations_v9.py','README_CORE_OPERATIONS_V9.md',
    'extract_core_job31.py','README_EXTRACT_CORE_JOB31.md',
    'prepare_core_publication_v8.py','review_core_publication_v8.py','README_CORE_PUBLICATION_V8.md']
SUBTREE_SOURCES=tuple('sqlite_sidecar_race_20261006/'+name for name in (
    'storage_support.py','test_sqlite_sidecar_race.py','run_host_sidecar_checks.py',
    'build_sidecar_package30.py','prepare_sidecar_stage30.py',
    'README_SQLITE_SIDECAR_RACE.md','README_SIDECAR_PACKAGE30.md','README_SIDECAR_STAGE30.md',
    'prepare_sidecar_stage30_v2.py','README_SIDECAR_STAGE30_V2.md'))
SUBTREE_SOURCES += tuple('caption_snapshot_20261006/'+name for name in (
    'installed_engine.py','d1_spatial_policy.py','d1_caption_snapshot.py',
    'check_d1_caption_snapshot.py','run_host_snapshot_checks.py',
    'README_D1_CAPTION_SNAPSHOT.md','build_caption_package31.py',
    'README_CAPTION_PACKAGE31.md','ops31/prepare_caption31.py',
    'ops31/README_CAPTION31_OPS.md'))
SUBTREE_SOURCES += tuple('capacity_gallery_20261006/'+name for name in (
    'installed_engine.py','personal_gallery.py','application_contract.py','capacity_personal_store.py',
    'gallery_worker.py','gallery_capacity_admission.py','README_GALLERY_CAPACITY_STORE.md',
    'README_GALLERY_WORKER_CAPACITY.md','test_capacity_personal_store.py','test_gallery_worker_capacity.py',
    'run_host_gallery_capacity.py','build_gallery_package32.py','README_GALLERY_PACKAGE32.md',
    'ops32/prepare_gallery32.py','ops32/README_GALLERY32_OPS.md'))
SUBTREE_SOURCES += tuple('event_writer_streaming_20261006/'+name for name in (
    'event_compaction.py','runtime_support.py','README_EVENT_WRITER_STREAMING.md',
    'test_event_writer_streaming.py','run_host_event_writer_checks.py',
    'build_event_package33.py','README_EVENT_PACKAGE33.md'))
SUBTREE_SOURCES += tuple('model_address_space_20261006/'+name for name in (
    'worker.py','native_scope.py','launch_raw_qualification_action.py','README_MODEL_ADDRESS_SPACE.md',
    'test_model_address_space.py','run_host_model_address_space_checks.py',
    'closed_unit_owner_as.py','README_CLOSED_UNIT_OWNER_AS.md'))
GUIDE_TARGETS=(C+'MODE_GUIDE.md',C+'BACKEND_COMBINATIONS.md',
    C+'INSTALL_HEALTH_AND_RECOVERY.md',C+'CHATGPT_HANDOFF.md',C+'FINAL_OPERATOR_GUIDE.md',
    L+'README_PIPELINES.md',L+'CORE_REPAIR_PIPELINE_NOTES.md',L+'CORE_REPAIR_TECHNICAL_NOTES.md',
    L+'RAM_RESOURCE_GUIDE.md',L+'pipelines/pyannote_redimnet.md',L+'pipelines/pyannote_titanet.md',
    L+'pipelines/current_delayed.md',L+'pipelines/chunk52_threads2.md')
ENTRY_TARGETS=('DELIVERY_START_HERE.md',C+'START_HERE_CURRENT.md',L+'START_HERE.md')
TRACKED=tuple(dict.fromkeys((*TRACKED,*GUIDE_TARGETS,*ENTRY_TARGETS)))
PRIVATE_PARTS=frozenset(('preserved','drafts','source','backup','restore','runtime-data',
    'models','galleries','recordings','__pycache__','source-backups','current_build33','current_build34','current_build35'))
PRIVATE_PREFIXES=('completion_docs_','entry_review_','audit-','operation-',
    'production-backup-','classic-ui-check-','full-app-hour-','publication-')
PUBLICATION_V3_PINS={
    'prepare_core_publication_v3.py':'84992726ec1c929952c2a306838b41bd7dd1173c8e19102aeaede5b3c08f1f30',
    'review_core_publication_v3.py':'65a55c9242db046417be546eae200e65bc52e3180baddb70947a13d42bc1a62f',
    'README_CORE_PUBLICATION_V3.md':'a65fa8346f3e200e72707bc116c780fb4e4b9d3349e90e03710e1d25e36f0fa3'}
PUBLICATION_V4_PINS={
    'prepare_core_publication_v4.py':'fe5b80f7740d5949a36429e341563f475f6dd6ddc45611c507e45d4244a1dbe9',
    'review_core_publication_v4.py':'950fef3fdad797c372148343b20f85043283a72eabe0c8d643b40fafa794bf8b',
    'README_CORE_PUBLICATION_V4.md':'44dd1f05fd6994548955c1a52c8518810f1d50214eb750c6163bd85aa0d50785'}
SELECTED += list(PUBLICATION_V4_PINS)+['host_core_operations_v10.py','README_CORE_OPERATIONS_V10.md']
SUBTREE_SOURCES += tuple('event_writer_streaming_20261006/ops33/'+name for name in (
    'prepare_event33_v2.py','README_EVENT33_OPS_V2.md'))
SELECTED += list(PUBLICATION_V3_PINS)+[
    'prepare_core_publication_v8.py','review_core_publication_v8.py','README_CORE_PUBLICATION_V8.md',
    'review_failed_hour05_prefix.py','README_FAILED_HOUR05_PREFIX.md']
PUBLICATION_V5_PINS={
    'prepare_core_publication_v5.py':'500a13c83935da40e9f7934bc731dc4f43e77a07c75e9ba67abf38c9730304e9',
    'review_core_publication_v5.py':'ccd4dd55e47f84027fe83a731ab2d0d46cf446679fd9b67ac565583dcdf38288',
    'README_CORE_PUBLICATION_V5.md':'93bff5161e61f12f8fe962e32cd3a85895b28170eda4063d9fe2505639b0410b'}
PUBLICATION_V6_PINS={
    'prepare_core_publication_v6.py':'62498dfdfa6fcfafa4debaba4680f07904c09dab3d3e0e993dada80262b9ad9c',
    'review_core_publication_v6.py':'d1339835cda21bb7f3c899d18c448acb78ba3dc400bf91ab28641d4df7da8655',
    'README_CORE_PUBLICATION_V6.md':'1ad58a120a55bb343dc17323dd669c9139c4b991c3ca894d4162d7a5d1958abe',
    'build_core_handoff_v6.py':'1b4dfff7a5b3146c7a78ac50e2d5eff05b095049dc265af41f0ad69bde7bd059'}
SELECTED += list(PUBLICATION_V5_PINS)+[
    'build_core_handoff_v6.py','build_core_handoff_v7.py',
    'host_core_operations_v11.py','README_CORE_OPERATIONS_V11.md',
    'README_VERIFY_PREPARED_RUNTIME_PACKAGE.md',
    'inspect_normal_manual_unit.py','README_NORMAL_MANUAL_INSPECTION.md',
    'normal_gui_control.py','launch_normal_gui_action.py',
    'prepare_normal_gui_workflow.py','README_NORMAL_GUI_WORKFLOW.md']
SELECTED += list(PUBLICATION_V6_PINS)+[
    'build_startup_package35.py','README_STARTUP_PACKAGE35.md',
    'host_core_operations_v12.py','README_CORE_OPERATIONS_V12.md',
    'inspect_live51_fault.py','README_LIVE51_FAULT.md']
NAMED_CONTROL_PINS={'CORE_STAGE35_ROOT_ADMISSION.json':
    '345d527c78033ea54946e5c8104420f3009515c34a8a179876e5cca8f9e11d70'}
CURRENT_OPERATOR_SOURCE_PINS={
    'host_core_operations_v12.py':'46732d020c5727515a04e56a69d06df86feefd40f7e654e890d5bae7a3764573',
    'normal_gui35_20261006/normal_gui_control.py':'d281ca84e7cc8b594f2ca6049c9fe0ea32d91b950ea8962bf2704c294aeffa84',
    'normal_gui35_20261006/launch_normal_gui_action.py':'79512f3c65920b85d1b9b10168a13252d87f780df55ea870e96abbfff38d050e',
    'normal_gui35_20261006/prepare_normal_gui_workflow.py':'e730ad7c31de8d006775fe9e2ff502602385fd60c178a6c5f666096a376d2157'}
# The sole new shell source is explicit; --extra-source stays Python/Markdown only.
NAMED_SHELL_SOURCES=('verify_prepared_runtime_package.ps1',)
NAMED_SHELL_PINS={'verify_prepared_runtime_package.ps1':
    '3519a7147e8bd8e817769bf5fa115867ce6973764ff4a143d224b5c504f896a2'}
SUBTREE_SOURCES += tuple('asr_metadata_cache_20261006/'+name for name in (
    'asr_segment_runtime.py','asr_metadata_cache.py','test_asr_metadata_cache.py',
    'run_host_asr_metadata_cache.py','README_ASR_METADATA_CACHE.md',
    'build_core_performance_package34.py','README_CORE_PERFORMANCE_PACKAGE34.md',
    'ops34/prepare_core_performance34.py','ops34/README_CORE_PERFORMANCE34_OPS.md'))
SUBTREE_SOURCES += tuple('s7_projection_copy_20261006/'+name for name in (
    's7_projection_copy.py','classic_frontend.py','test_s7_projection_copy.py',
    'run_host_s7_projection_copy.py','README_S7_PROJECTION_COPY.md'))
SUBTREE_SOURCES += tuple('disk_capacity_policy_20261006/'+name for name in (
    'nemotron_binding.py','profiles.py','telemetry.py','installed_engine.py',
    'application_controller.py','release_authorization.py','launcher.py','capacity_drain_profile.py',
    'README_DISK_CAPACITY_POLICY.md','test_disk_capacity_policy.py','run_host_disk_capacity_checks.py'))
SUBTREE_SOURCES += tuple('xvf_fresh_start_20261006/'+name for name in (
    'launcher.py','xvf_readiness_helper.py','README_XVF_FRESH_START.md',
    'test_xvf_fresh_start.py','run_host_xvf_fresh_start.py',
    'classic_frontend.py','README_CLASSIC_STORAGE_COPY35.md',
    'ops35/prepare_xvf_startup35.py','ops35/README_XVF_STARTUP35_OPS.md'))
SUBTREE_SOURCES += tuple('normal_gui35_20261006/'+name for name in (
    'normal_gui_control.py','launch_normal_gui_action.py',
    'prepare_normal_gui_workflow.py','README_NORMAL_GUI_WORKFLOW.md'))
PUBLICATION_V7_PINS={
    'prepare_core_publication_v7.py':'7b7b484a48498447e5301fc45525cd5efa78e0efbfbd077810917ac877b27a16',
    'review_core_publication_v7.py':'706130a3307bcacc0ac9978c7c85338069142d9f05676e696c3d076cc668f7b9',
    'README_CORE_PUBLICATION_V7.md':'148d520d50699a09be4091d60e7ed987ab5a1775ba92762be87590404fdc729e',
    'build_core_handoff_v7.py':'b2b5bc5cf284b778a2bb67fc8c9695babc765a1c775b41154eae5e49443855c7',
}
SELECTED += list(PUBLICATION_V7_PINS)
HOUR08_SOURCE_PINS={
    'hour08_pc_reservation_20261006/activate_core_desktop_action35.py':'035951d5b348dd24506cab4339a79ac6057c95932cdc17b4a52dfc19e808f011',
    'hour08_pc_reservation_20261006/core_database_recovery.py':'1b1f8127737ea47c77978e007c0c82f87e3ab4851e2ae15b013ba4a28a04adbc',
    'hour08_pc_reservation_20261006/extract_core_job35.py':'0155d4ec54941b6696cd38c27e1220bfd8fd7d796285c74a30aa36c997430d8f',
    'hour08_pc_reservation_20261006/launch_core_full_app_hour35.py':'5d1a683a43d55166781a6f81935713cb960b3f7292e0cd17974c1dc6e493efc0',
    'hour08_pc_reservation_20261006/launch_full_app_soak_action.py':'5d1a683a43d55166781a6f81935713cb960b3f7292e0cd17974c1dc6e493efc0',
    'hour08_pc_reservation_20261006/monitor_native_job_hour08.py':'f421918b541b3973e112df1f59820d53d040559160472f2d293629d168930218',
    'hour08_pc_reservation_20261006/native_core_live_check_v2.py':'5c6eab13e00076aabf3f022f69410e1f330dc16a4cbad69b49b8fe016109e37e',
    'hour08_pc_reservation_20261006/native_core_saved_check_v2.py':'01fc4288e8496a99eb318875e1aaebac51af8b2fca80b232798693d93cc27237',
    'hour08_pc_reservation_20261006/native_job_probe.py':'65f74d4c3928c64190a61b195e2e76967a00d9210a40d0103bff07076d44e5e1',
    'hour08_pc_reservation_20261006/prepare_core_activation35.py':'4cda9aa02b3a0cea77153f3eaaaa7f71a009aa399086fccc4bc4bff7a061a7e8',
    'hour08_pc_reservation_20261006/prepare_core_endurance35.py':'688d00b11788dae0a2556f3596dafe9618e70586be77ebd28ea87c286ae905fd',
    'hour08_pc_reservation_20261006/prepare_core_native_validation_v35.py':'aa7f248238a94a44c8ba6477e3a0fcdc0ab023645d78628a996e3d55c9d3daa2',
    'hour08_pc_reservation_20261006/prepare_core_stage35.py':'7302b8be728a58f6a0243b693dec990a2d168a04d034459185e2319e374162be',
    'hour08_pc_reservation_20261006/README_CORE_BUILD35_HELPERS.md':'21374e9657b4e42c2695fce1566f41844fa6b7f83faa9b3dc4855a9dd9dd5fbb',
    'hour08_pc_reservation_20261006/README_HOUR08_PC_RESERVATION.md':'e235e8a50b24868a08562ac0d0514d83a5744c93f6899d787ef86a1929910f6e',
    'hour08_pc_reservation_20261006/README_JOB_MONITOR.md':'2861d98f492b57f6d6ada631ac52bb396759954da84c4c3f6b9ce251ef08c83c',
    'hour08_pc_reservation_20261006/review_core_full_app_hour35.py':'e6f4b5e398fc86225d7576c3d1cd8c8a7f6d9373141d74bfa7a9d4917393954c',
    'hour08_pc_reservation_20261006/stage_c24_endurance_input35.py':'a86b0e2574494eaf7de4d84885a8d06649de36edb2416f8a65b8956bf46e7504',
}
SUBTREE_SOURCES += tuple(HOUR08_SOURCE_PINS)
CURRENT_OPERATOR_SOURCE_PINS.update(HOUR08_SOURCE_PINS)

SELECTED=list(dict.fromkeys(SELECTED))
CURRENT_TARGET='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-35'
CURRENT_PARENT_PIN='fb9ca63814906629ec9e93935f4d28e77d1c60e1f6202f212223116195a0e802'
CURRENT_REPLACEMENTS=frozenset(('launcher.py','xvf_readiness_helper.py','README_XVF_FRESH_START.md',
    'classic_frontend.py','README_CLASSIC_STORAGE_COPY35.md'))
CURRENT_PINS={
    'current_manifest_sha256':'5e4b8f21a0cbd04bedbccc6c2504cee7910fc60deda09c4777dc9ffe07c05e3f',
    'current_content_sha256':'8f21cdb44aa0944422e0a5e592a3888e9e8f90ed77c4aeb2f07d33fcbada4bd2',
    'current_source_review_sha256':'61564263badf03c5a5ba696419e7b45ff7a85e5e749ee950129dd8a271885ee7',
    'current_build_result_sha256':'d3e957c025468192ec4d860685935591a83ca02e17eee1bd9d9e728c537d4810',
    'current_build_closure_sha256':'12f6f5dc4eaaa0eb99cc1d4e05ad79655f4cab4fcdbaa8a062579cc299a63b7f',
    'current_archive_sha256':'6d9bb8f5fc2a571d0911eddf3d2f13f555d682d224af7e58fcbe2d7a7ea7a76a'}
HISTORICAL33_PACKAGE=Q/'audit-preparation/event-package33-efdac72ba11f4e8e93b519e80dc3898a/package'
HISTORICAL33_SOURCE_REVIEW=HISTORICAL33_PACKAGE.parent/'SOURCE_DIFF_REVIEW.json'
HISTORICAL33_SOURCE_REVIEW_SHA='b81455d495220ed8b64632fd2fb5b33954cc0be9bc62f6af8cdf879934340905'
HISTORICAL33_PIN='2889a2bddc9b6cb65c150510e87db978eb5fb24e4ffa22809b1623d45234b61e'
HISTORICAL33_CONTENT_SHA='8b0eefd6ffa5a0749a1eeaf607e9454efd5fa16cbf76d373fcbb1fe22d759631'
HISTORICAL34_PACKAGE=Q/'audit-preparation/core-performance-package34-fd1c79ff6e7f4a28b461c329a0b36e14/package'
HISTORICAL34_PINS={
    'manifest':'fb9ca63814906629ec9e93935f4d28e77d1c60e1f6202f212223116195a0e802',
    'content':'aec9d81d0208b608ebe1a0c43ec4d67ebeb04811f4b5e54187ee8616b3dce9d1',
    'source_review':'53275087e72069b6d3012f505616079ab8debaa90a290848f1830e159e9c6096',
    'build_closure':'923c2d77c1c9cba03a88dad3075aaf15de994665c7b15c37c2dedfb0c8ed7aa4'}
HANDOFF_ADAPTER=HERE/'build_core_handoff_v7.py'
HANDOFF_ADAPTER_SHA='b2b5bc5cf284b778a2bb67fc8c9695babc765a1c775b41154eae5e49443855c7'
CURRENT_CONTROL_JSON=frozenset(('BINDING.json','BUILD_OPTIONS.json',*(
    'profiles/'+name+'.json' for name in ('baseline','baseline-anonymous','baseline-titanet',
    'd1-anonymous','d1-delayed','d1-delayed-titanet','d1-streaming-saved',
    'd1-streaming-titanet-saved','d1-chunk52-saved','d1-chunk52-titanet-saved'))))
CURRENT_ARGUMENTS=('current_package','current_manifest_sha256','current_content_sha256',
    'current_source_review','current_source_review_sha256','current_build_result',
    'current_build_result_sha256','current_build_closure','current_build_closure_sha256',
    'current_archive','current_archive_sha256','current_members_file','current_members_sha256')
CURRENT_PATH_ARGUMENTS=frozenset(('current_package','current_source_review','current_build_result',
    'current_build_closure','current_archive','current_members_file'))
CURRENT_MIRROR=HERE/'current_build35'

def extra_source_path(name):
    rel=PurePosixPath(name)
    if (not name or rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name
            or rel.as_posix()!=name or rel.suffix not in {'.py','.md'}
            or any(part.casefold() in PRIVATE_PARTS or
                   part.casefold().startswith(PRIVATE_PREFIXES) for part in rel.parts)):
        raise ValueError('Explicit public D code/Markdown path required; private/draft trees excluded')
    return HERE.joinpath(*rel.parts)

def encoded(value):return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def strict(raw):
    def pairs(rows):
        out={}
        for key,value in rows:
            if key in out:raise ValueError('Duplicate plan key')
            out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))
def read(path,maximum=2*1024**2):
    before=path.lstat();resolved=path.resolve(strict=True)
    if (path.is_symlink() or any(p.is_symlink() for p in path.parents) or not stat.S_ISREG(before.st_mode)
        or before.st_nlink!=1 or before.st_size>maximum or os.path.normcase(str(path.absolute()))!=os.path.normcase(str(resolved))):raise ValueError('Canonical bounded ordinary source required: '+str(path))
    raw=path.read_bytes();after=path.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns) or len(raw)!=before.st_size:raise ValueError('Source changed during plan snapshot')
    return raw

def archive_hash(path):
    """Hash the separate deployment asset without copying it into the public source plan."""
    before=path.lstat();resolved=path.resolve(strict=True)
    if (path.is_symlink() or any(p.is_symlink() for p in path.parents)
            or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1
            or not 0<before.st_size<=16*1024**2
            or os.path.normcase(str(path.absolute()))!=os.path.normcase(str(resolved))):
        raise ValueError('Canonical bounded ordinary deployment archive required')
    digest=hashlib.sha256();count=0
    with path.open('rb') as stream:
        for raw in iter(lambda:stream.read(65536),b''):
            count+=len(raw);digest.update(raw)
    after=path.stat()
    if ((before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns)
            or count!=before.st_size):raise ValueError('Deployment asset changed during hash readback')
    return digest.hexdigest(),count

def current_member_path(name):
    rel=PurePosixPath(name)
    if (not name or rel.is_absolute() or '..' in rel.parts or '\\' in name or ':' in name
            or rel.as_posix()!=name or any(part.casefold() in PRIVATE_PARTS
                or part.casefold().startswith(PRIVATE_PREFIXES) for part in rel.parts)
            or any('.backup' in part.casefold() or '.restore' in part.casefold() for part in rel.parts)
            or (rel.suffix not in {'.py','.md'} and name not in CURRENT_CONTROL_JSON)):
        raise ValueError('Explicit current Python/Markdown or named control/profile JSON required')
    return rel

def current_arguments(value):
    if type(value) is not dict or set(value)!=set(CURRENT_ARGUMENTS):
        raise ValueError('Exact current build35 argument inventory required')
    return argparse.Namespace(**{name:Path(body) if name in CURRENT_PATH_ARGUMENTS else body
        for name,body in value.items()})

def verify_current(args):
    """Bind actual sealed35 source, independent closure and the separate installer asset."""
    for name in CURRENT_ARGUMENTS:
        value=getattr(args,name)
        if name not in CURRENT_PATH_ARGUMENTS and (type(value) is not str
                or re.fullmatch('[0-9a-f]{64}',value) is None):
            raise ValueError('Explicit actual current build/source/archive pins required')
    if any(getattr(args,name)!=pin for name,pin in CURRENT_PINS.items()):
        raise ValueError('Only the actual root-reviewed sealed build35 is current')
    package=args.current_package
    if (package.name!='package' or package.parent.parent!=Q/'audit-preparation'
            or package.resolve(strict=True)!=package):raise ValueError('Canonical actual sealed package required')
    for path,name,pin in ((package/'PACKAGE_MANIFEST.json','manifest',args.current_manifest_sha256),
            (args.current_source_review,'source_review',args.current_source_review_sha256),
            (args.current_build_result,'build_result',args.current_build_result_sha256),
            (args.current_build_closure,'build_closure',args.current_build_closure_sha256)):
        raw=read(path)
        if sha(raw)!=pin:raise ValueError('Actual current '+name+' pin differs')
        if path.parent!=package.parent and name!='manifest':
            raise ValueError('Current package/source/closure must share the exact build root')
    manifest=strict(read(package/'PACKAGE_MANIFEST.json'))
    review=strict(read(args.current_source_review));result=strict(read(args.current_build_result))
    closure=strict(read(args.current_build_closure));owner=strict(read(package.parent/'REGISTERED_OWNER.json'))
    closed=strict(read(package.parent/'SOURCE_CLOSED.json'))
    binding=strict(read(package/'BINDING.json'));provenance=strict(read(package/'REPAIR_PROVENANCE.json'))
    historical_binding=strict(read(HISTORICAL34_PACKAGE/'BINDING.json'))
    historical_acceptance=strict(read(HISTORICAL34_PACKAGE/'PRODUCTION_ACCEPTANCE.json'))
    historical_provenance=strict(read(HISTORICAL34_PACKAGE/'REPAIR_PROVENANCE.json'))
    acceptance=strict(read(package/'PRODUCTION_ACCEPTANCE.json'))
    preservation=strict(read(package.parent/'BUILD34_MEMBER_PRESERVATION.json'))
    files=manifest.get('files')
    if (owner.get('schema')!='just-peachy.host-registered-owner.v1' or owner.get('cpu')!=14
            or owner.get('affinity_mask')!=16384 or any(type(owner.get(name)) is not int
                or owner[name]<=0 for name in ('pid','creation_filetime'))):
        raise ValueError('Actual registered current build owner required')
    if (type(files) is not list or len(files)>4096 or not files
            or manifest.get('target')!=CURRENT_TARGET or binding.get('target')!=CURRENT_TARGET
            or manifest.get('candidate_content_sha256')!=args.current_content_sha256
            or binding.get('candidate_content_sha256')!=args.current_content_sha256
            or review.get('schema')!='just-peachy.xvf-startup-package-source-review.v1'
            or review.get('target')!=CURRENT_TARGET or review.get('parent_manifest_sha256')!=CURRENT_PARENT_PIN
            or set(review.get('replacement_pins',{}))!=CURRENT_REPLACEMENTS
            or provenance.get('parent_manifest_sha256')!=CURRENT_PARENT_PIN
            or provenance.get('source_review_sha256')!=args.current_source_review_sha256
            or provenance.get('schema')!='just-peachy.xvf-startup-runtime-repair.v1'
            or provenance.get('model_address_space_policy_changed') is not False
            or provenance.get('physical_ram_disk_and_model_address_space_ceiling_changed') is not False
            or provenance.get('resource_storage_policy_changed') is not False
            or provenance.get('normal_capture_backlog_and_drain_policy_changed') is not False
            or provenance.get('startup_recovery_policy_changed') is not True
            or provenance.get('durable_sql_fsync_event_content_or_model_inputs_relaxed') is not False):
        raise ValueError('Actual current build35 target/content/parent/source identity differs')
    if (len(review.get('source_pins',{}))!=24 or len(files)!=448
            or preservation.get('parent_manifest_sha256')!=CURRENT_PARENT_PIN
            or preservation.get('removed_members')!=[]
            or preservation.get('all_other_parent_members_byte_identical') is not True
            or preservation.get('binding_and_acceptance_limits_structure_preserved') is not True
            or binding.get('limits')!=historical_binding.get('limits')
            or acceptance.get('limits')!=historical_acceptance.get('limits')
            or provenance.get('retained_model_address_space_policy')!=historical_provenance.get('retained_model_address_space_policy')
            or provenance.get('retained_performance_policy')!=historical_provenance.get('performance_policy')
            or provenance.get('focused_host_tests')!=review.get('focused_host_tests')
            or provenance.get('reused_build34_focused_host_tests')!=historical_provenance.get('focused_host_tests')
            or review.get('focused_host_tests',{}).get('schema')!='just-peachy.xvf-fresh-start-host.v1'
            or review.get('focused_host_tests',{}).get('tests')!=19
            or review.get('focused_host_tests',{}).get('source_count')!=452
            or review.get('focused_host_tests',{}).get('exact_owner_closed') is not True
            or review.get('frontend_wording_review',{}).get('whole_reverse_text_equal') is not True
            or review.get('frontend_wording_review',{}).get('host19_coverage_claimed') is not False):
        raise ValueError('Exact current35 source count, parent preservation and retained ceilings required')
    inventory={row['path']:row for row in files}
    if len(inventory)!=len(files) or len({name.casefold() for name in inventory})!=len(files):
        raise ValueError('Unique sealed current package inventory required')
    expanded_bytes=sum(row['bytes'] for row in files)+len(read(package/'PACKAGE_MANIFEST.json'))
    for name,value in review['source_pins'].items():
        source=read(Path(value['path']))
        if (len(source),sha(source))!=(value['bytes'],value['sha256']):
            raise ValueError('Frozen current35 input changed: '+name)
        for side in ('backup','restore'):
            if read(package.parent/'prepared-source'/side/name)!=source:
                raise ValueError('Current35 independent source snapshot differs: '+name)
    for name,value in review['replacement_pins'].items():
        source=read(package/name)
        if ((len(source),sha(source))!=(value['bytes'],value['sha256'])
                or name not in inventory or inventory[name]['bytes']!=len(source)
                or inventory[name]['sha256']!=sha(source)):
            raise ValueError('Current replacement differs from source review/package: '+name)
    if (result.get('manifest_sha256')!=args.current_manifest_sha256
            or result.get('candidate_content_sha256')!=args.current_content_sha256
            or result.get('parent_manifest_sha256')!=CURRENT_PARENT_PIN
            or result.get('target')!=CURRENT_TARGET or Path(result.get('package',''))!=package
            or result.get('files')!=len(files) or result.get('source_backups_and_restores_exact') is not True
            or result.get('archive_members_independently_restored')!=len(files)+1
            or result.get('archive_sha256')!=args.current_archive_sha256
            or Path(result.get('archive',''))!=args.current_archive
            or result.get('installed') is not False or result.get('native_qualified') is not False
            or closure.get('schema')!='just-peachy.core-package35-independent-closure.v1'
            or closure.get('owner')!=owner or type(closure.get('builder_natural_exit_code')) is not int
            or closure.get('builder_natural_exit_code')!=0
            or closure.get('builder_os_process_absent') is not True
            or closure.get('validator_sha256')!=NAMED_SHELL_PINS['verify_prepared_runtime_package.ps1']
            or closure.get('source_backups_and_independent_restores_exact') is not True
            or closure.get('current_sources_unchanged') is not True
            or closure.get('manifest_sha256')!=args.current_manifest_sha256
            or closure.get('source_review_sha256')!=args.current_source_review_sha256
            or closure.get('archive_sha256')!=args.current_archive_sha256
            or closure.get('source_inputs')!=len(review['source_pins'])
            or closure.get('archive_members_readback')!=len(files)+1
            or closure.get('archive_expanded_bytes')!=expanded_bytes
            or closure.get('independent_expanded_restore_exact') is not True
            or closure.get('native_action') is not False
            or closed.get('scope_closed') is not True or closed.get('native_action') is not False):
        raise ValueError('Actual independently closed build35 preparation/restore required')
    asset_sha,asset_bytes=archive_hash(args.current_archive)
    if (asset_sha!=args.current_archive_sha256
            or args.current_archive.parent!=package.parent):
        raise ValueError('Separate deployment archive identity/readback differs')
    selection=read(args.current_members_file)
    if sha(selection)!=args.current_members_sha256:raise ValueError('Root-reviewed exact current source member list differs')
    names=selection.decode('utf-8').splitlines()
    if (not names or len(names)>4096 or len(names)!=len(set(names))
            or len({name.casefold() for name in names})!=len(names)):
        raise ValueError('Explicit unique current source selection required')
    required_current=CURRENT_REPLACEMENTS|CURRENT_CONTROL_JSON|{
        name for name in inventory if name.endswith('.py')}
    if not required_current<=set(names):
        raise ValueError('All package Python, five changed source/README members and named controls/profiles required')
    selected=[];selected_bytes=0
    for name in names:
        rel=current_member_path(name)
        if name not in inventory:raise ValueError('Selected source absent from sealed package: '+name)
        raw=read(package.joinpath(*rel.parts));raw.decode('utf-8')
        if (len(raw),sha(raw))!=(inventory[name]['bytes'],inventory[name]['sha256']):
            raise ValueError('Selected current source differs from manifest: '+name)
        if rel.suffix=='.json':strict(raw)
        selected_bytes+=len(raw)
        if selected_bytes>8*1024**2:raise ValueError('Finite8MiB current public source mirror')
        selected.append(dict(path=name,bytes=len(raw),sha256=sha(raw)))
    return dict(schema='just-peachy.current-public-source-map.v1',build=35,target=CURRENT_TARGET,
        arguments={name:str(getattr(args,name)) for name in CURRENT_ARGUMENTS},
        deployment_members=len(files)+1,selected_source_members=len(selected),selected_source_bytes=selected_bytes,
        deployment_expanded_bytes=expanded_bytes,
        separate_deployment_archive_bytes=asset_bytes,source_mirror=str(CURRENT_MIRROR),files=selected,
        package_controls_not_copied={name:inventory[name]['sha256'] for name in
            ('PRODUCTION_ACCEPTANCE.json','RELOCATION_CERTIFICATE.json','REPAIR_PROVENANCE.json') if name in inventory},
        source_only=True,complete_deployment_bundle_included=False,native_qualification_inferred=False)

def source_map_bytes(current):
    args=current['arguments']
    lines=['# Current build35 source mirror','',
        'Selected code, Markdown and reviewed control/profile JSON copied byte-for-byte from the sealed package.',
        'This directory is a source handoff. It does not contain the complete deployment package, models, galleries, recordings or private receipts.',
        'Source/package identity checks do not qualify native operation. Current outcomes and limits are in ../CORE_REPAIR_RESULTS.md.','',
        '- Native target: `'+current['target']+'`.',
        '- Sealed package source: `'+args['current_package']+'`.',
        '- Manifest SHA256: `'+args['current_manifest_sha256']+'`.',
        '- Candidate content SHA256: `'+args['current_content_sha256']+'`.',
        '- Source review: `'+args['current_source_review']+'`; SHA256 `'+args['current_source_review_sha256']+'`.',
        '- Closed build receipt: `'+args['current_build_result']+'`; SHA256 `'+args['current_build_result_sha256']+'`.',
        '- Independent closure: `'+args['current_build_closure']+'`; SHA256 `'+args['current_build_closure_sha256']+'`.',
        '- Separate installer asset: `'+args['current_archive']+'`; SHA256 `'+args['current_archive_sha256']+'`.',
        '- Installer asset bytes: '+str(current['separate_deployment_archive_bytes'])+'.',
        '- Full deployment members: '+str(current['deployment_members'])+'; selected source members: '+str(current['selected_source_members'])+'.',
        '- Exact selection-list SHA256: `'+args['current_members_sha256']+'`.','',
        'Runtime source is under this directory; historical repair and test procedures remain in the parent and named repair subdirectories.',
        'Deployment acceptance, relocation and repair receipts stay external. Their package hashes are:', '']
    lines.extend('- `'+name+'`: `'+pin+'`.' for name,pin in sorted(current['package_controls_not_copied'].items()))
    lines+=['','| Selected package path | Bytes | SHA256 |','| --- | ---: | --- |']
    lines.extend('| ['+row['path']+']('+row['path']+') | '+str(row['bytes'])+' | `'+row['sha256']+'` |' for row in current['files'])
    return ('\n'.join(lines)+'\n').encode('utf-8')

def mirror_current(current,package):
    """Create only selected public source files; existing differing bytes are never overwritten."""
    expected={row['path'] for row in current['files']}|{'SOURCE_MAP.md'}
    if CURRENT_MIRROR.exists():
        if CURRENT_MIRROR.resolve(strict=True)!=CURRENT_MIRROR or not CURRENT_MIRROR.is_dir():
            raise ValueError('Ordinary canonical current source mirror required')
        actual=set()
        for folder,dirs,files in os.walk(CURRENT_MIRROR,followlinks=False):
            for name in dirs:
                path=Path(folder)/name
                if path.resolve(strict=True)!=path or path.is_symlink():raise ValueError('No links in current mirror')
            actual.update((Path(folder)/name).relative_to(CURRENT_MIRROR).as_posix() for name in files)
        if actual-expected:raise ValueError('Unexpected existing current mirror files; preserve and use root review')
    paths=[];written=0;directories={CURRENT_MIRROR}
    for row in (*current['files'],dict(path='SOURCE_MAP.md')):
        name=row['path'];path=CURRENT_MIRROR.joinpath(*PurePosixPath(name).parts)
        raw=source_map_bytes(current) if name=='SOURCE_MAP.md' else read(package.joinpath(*PurePosixPath(name).parts))
        written+=len(raw)
        directories.update(parent for parent in path.parents if parent==CURRENT_MIRROR or parent.is_relative_to(CURRENT_MIRROR))
        if written+len(directories)*65536>8*1024**2:
            raise ValueError('Finite8MiB mirror including source map/directory reservations')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+24*1024**2:raise OSError('Original host floor plus exact source/plan reservations')
        if path.exists():
            if read(path)!=raw:raise ValueError('Existing current source mirror differs; no overwrite: '+name)
        else:
            if path.parent.resolve()!=path.parent:raise ValueError('Canonical mirror parent required before mkdir')
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.parent.resolve(strict=True)!=path.parent:raise ValueError('Canonical mirror parent required')
            with path.open('xb') as stream:
                if stream.write(raw)!=len(raw):raise OSError('Short current source mirror write')
                stream.flush();os.fsync(stream.fileno())
        if read(path)!=raw:raise OSError('Independent current source mirror readback differs')
        paths.append(path)
    return paths

def verify_frozen_sources():
    """Preserve all three immutable source generations and bind actual build31 bytes."""
    for name,pin in PUBLICATION_V3_PINS.items():
        if sha(read(HERE/name))!=pin:raise ValueError('Immutable publicationV3 source changed: '+name)
    for name,pin in PUBLICATION_V4_PINS.items():
        if sha(read(HERE/name))!=pin:raise ValueError('Immutable publicationV4 source changed: '+name)
    for name,pin in PUBLICATION_V5_PINS.items():
        if sha(read(HERE/name))!=pin:raise ValueError('Immutable publicationV5 source changed: '+name)
    reviews=[]
    for path,pin,root,expected_inputs,expected_replacements in (
            (PARENT_SOURCE_REVIEW,PARENT_SOURCE_REVIEW_SHA,HERE,27,24),
            (MIDDLE_SOURCE_REVIEW,MIDDLE_SOURCE_REVIEW_SHA,MIDDLE_REPLACEMENT_ROOT,10,2),
            (SOURCE_REVIEW,SOURCE_REVIEW_SHA,REPLACEMENT_ROOT,13,4)):
        raw=read(path)
        if sha(raw)!=pin:raise ValueError('Root-approved immutable source review changed')
        document=strict(raw)
        if (len(document['source_pins'])!=expected_inputs or
                len(document['replacement_pins'])!=expected_replacements):
            raise ValueError('Exact parent/current source inventory required')
        for name,value in document['source_pins'].items():
            source=read(Path(value['path']))
            if (len(source),sha(source))!=(value['bytes'],value['sha256']):
                raise ValueError('Frozen build source/evidence changed: '+name)
        for name,value in document['replacement_pins'].items():
            source=read(root/name)
            if (len(source),sha(source))!=(value['bytes'],value['sha256']):
                raise ValueError('Frozen runtime replacement changed: '+name)
        reviews.append(document)
    manifest_raw=read(PACKAGE/'PACKAGE_MANIFEST.json')
    if sha(manifest_raw)!=PIN:raise ValueError('Exact immutable build31 manifest required')
    manifest=strict(manifest_raw)
    binding=strict(read(PACKAGE/'BINDING.json'))
    provenance=strict(read(PACKAGE/'REPAIR_PROVENANCE.json'))
    if (manifest.get('target')!=binding.get('target') or
            manifest.get('target')!='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-31' or
            manifest.get('candidate_content_sha256')!=PACKAGE_CONTENT_SHA or
            binding.get('candidate_content_sha256')!=PACKAGE_CONTENT_SHA or
            provenance.get('parent_manifest_sha256')!=PARENT_PIN or
            provenance.get('source_review_sha256')!=SOURCE_REVIEW_SHA):
        raise ValueError('Actual build31 target/content/parent/source binding differs')
    for name,value in reviews[2]['replacement_pins'].items():
        source=read(PACKAGE/name)
        if (len(source),sha(source))!=(value['bytes'],value['sha256']):
            raise ValueError('Actual package replacement differs from frozen current source')
    return reviews

def verify_historical33():
    """Keep the failed-hour build33 source proof historical and byte exact."""
    raw=read(HISTORICAL33_SOURCE_REVIEW)
    if sha(raw)!=HISTORICAL33_SOURCE_REVIEW_SHA:raise ValueError('Immutable build33 source review differs')
    document=strict(raw)
    manifest_raw=read(HISTORICAL33_PACKAGE/'PACKAGE_MANIFEST.json')
    manifest=strict(manifest_raw)
    if (sha(manifest_raw)!=HISTORICAL33_PIN
            or manifest.get('candidate_content_sha256')!=HISTORICAL33_CONTENT_SHA
            or len(document.get('source_pins',{}))!=30
            or len(document.get('replacement_pins',{}))!=7):
        raise ValueError('Exact historical build33 package/source inventory required')
    for name,value in document['source_pins'].items():
        source=read(Path(value['path']))
        if (len(source),sha(source))!=(value['bytes'],value['sha256']):
            raise ValueError('Frozen build33 source changed: '+name)
    for name,value in document['replacement_pins'].items():
        source=read(HISTORICAL33_PACKAGE/name)
        if (len(source),sha(source))!=(value['bytes'],value['sha256']):
            raise ValueError('Historical build33 replacement changed: '+name)
    return document

def verify_historical34():
    """Keep staged34 and its failed51 startup scope historical and immutable."""
    manifest_raw=read(HISTORICAL34_PACKAGE/'PACKAGE_MANIFEST.json')
    review_raw=read(HISTORICAL34_PACKAGE.parent/'SOURCE_DIFF_REVIEW.json')
    closure_raw=read(HISTORICAL34_PACKAGE.parent/'INDEPENDENT_CLOSURE.json')
    manifest=strict(manifest_raw);document=strict(review_raw);closure=strict(closure_raw)
    if (sha(manifest_raw)!=HISTORICAL34_PINS['manifest']
            or sha(review_raw)!=HISTORICAL34_PINS['source_review']
            or sha(closure_raw)!=HISTORICAL34_PINS['build_closure']
            or manifest.get('candidate_content_sha256')!=HISTORICAL34_PINS['content']
            or len(manifest.get('files',[]))!=446
            or document.get('schema')!='just-peachy.core-performance-package-source-review.v1'
            or len(document.get('source_pins',{}))!=41
            or len(document.get('replacement_pins',{}))!=15
            or closure.get('schema')!='just-peachy.core-package34-independent-closure.v1'
            or closure.get('archive_members_readback')!=447 or closure.get('archive_expanded_bytes')!=7492370
            or closure.get('independent_expanded_restore_exact') is not True):
        raise ValueError('Exact historical34 package/source/closure inventory required')
    for name,value in document['source_pins'].items():
        source=read(Path(value['path']))
        if (len(source),sha(source))!=(value['bytes'],value['sha256']):
            raise ValueError('Frozen build34 source changed: '+name)
        for side in ('backup','restore'):
            if read(HISTORICAL34_PACKAGE.parent/'prepared-source'/side/name)!=source:
                raise ValueError('Historical34 independent source snapshot differs: '+name)
    for name,value in document['replacement_pins'].items():
        source=read(HISTORICAL34_PACKAGE/name)
        if (len(source),sha(source))!=(value['bytes'],value['sha256']):
            raise ValueError('Historical build34 replacement changed: '+name)
    return document

def verify_named_controls():
    """Admit the single root-selected public stage certificate, no other JSON."""
    for name,pin in PUBLICATION_V7_PINS.items():
        if sha(read(HERE/name))!=pin:
            raise ValueError('Frozen publicationV7 source differs: '+name)
    for name,pin in CURRENT_OPERATOR_SOURCE_PINS.items():
        if sha(read(HERE.joinpath(*PurePosixPath(name).parts)))!=pin:
            raise ValueError('Exact current35 operator source differs: '+name)
    for name,pin in NAMED_CONTROL_PINS.items():
        raw=read(HERE/name)
        if sha(raw)!=pin:raise ValueError('Exact named public stage certificate differs')
        value=strict(raw)
        if (value.get('schema')!='just-peachy.core-stage35-root-admission.v1'
                or value.get('label')!='core-stage35-01' or value.get('target')!=CURRENT_TARGET
                or value.get('manifest_sha256')!=CURRENT_PINS['current_manifest_sha256']
                or value.get('parent_manifest_sha256')!=CURRENT_PARENT_PIN
                or value.get('source_review_sha256')!=CURRENT_PINS['current_source_review_sha256']
                or value.get('archive_sha256')!=CURRENT_PINS['current_archive_sha256']
                or value.get('members')!=449 or value.get('expanded_bytes')!=7425000):
            raise ValueError('Current35 measured stage certificate/source linkage differs')
    return list(NAMED_CONTROL_PINS)

def verify_handoff_adapter():
    raw=read(HANDOFF_ADAPTER)
    if sha(raw)!=HANDOFF_ADAPTER_SHA:raise ValueError('Exact purpose-only35 handoff adapter required')
    restored=raw.replace(b'reviewed35 handoff',b'reviewed34 handoff').replace(
        b'README_CORE_PUBLICATION_V7.md',b'README_CORE_PUBLICATION_V6.md')
    if restored!=read(HERE/'build_core_handoff_v6.py'):
        raise ValueError('Final archive adapter purpose/pairedREADME whole reverse proof differs')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--label',required=True)
    parser.add_argument('--results-summary',type=Path,required=True,help='Final reviewed aggregate Markdown findings, without private content')
    parser.add_argument('--results-summary-sha256',required=True)
    parser.add_argument('--extra-source',action='append',default=[],help='Explicit D-relative additional code/Markdown only; no globs')
    for name in CURRENT_ARGUMENTS:
        parser.add_argument('--'+name.replace('_','-'),required=True,
            type=Path if name in CURRENT_PATH_ARGUMENTS else str)
    args=parser.parse_args()
    if (re.fullmatch(r'[a-z][a-z0-9-]{0,63}',args.label) is None
        or re.fullmatch('[0-9a-f]{64}',args.results_summary_sha256) is None):raise ValueError('Fresh canonical plan label and explicit final-results pin required')
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    _k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not _k.GetProcessTimes(_h,*(ctypes.byref(s) for s in stamps)):raise ctypes.WinError(ctypes.get_last_error())
    out=Q/'audit-preparation'/(args.label+'-'+uuid.uuid4().hex);out.mkdir()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=stamps[0].value,create_time=(stamps[0].value-116444736000000000)/10000000)
    with (out/'REGISTERED_OWNER.json').open('xb') as stream:
        raw=encoded(owner);stream.write(raw);stream.flush();os.fsync(stream.fileno())
    started=time.monotonic();written=len(raw)+65536;directories={out}
    def put(name,raw):
        nonlocal written
        path=out.joinpath(*PurePosixPath(name).parts)
        if path.is_relative_to(out) is not True:raise ValueError('Owned output only')
        pending=[p for p in path.parents if p!=out and p.is_relative_to(out) and p not in directories]
        if written+len(raw)+len(pending)*65536>16*1024**2 or time.monotonic()-started>600:raise OSError('Finite16MiB includingdirectories/600s plan scope')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+16*1024**2:raise OSError('Original host floor')
        path.parent.mkdir(parents=True,exist_ok=True);directories.update(pending);written+=len(pending)*65536
        with path.open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short publication-plan write')
            stream.flush();os.fsync(stream.fileno())
        written+=len(raw)
        if read(path,16*1024**2)!=raw:raise OSError('Independent publication-plan readback differs')
    put('HOST_SCOPE.json',encoded(dict(maximum_bytes=16*1024**2,maximum_seconds=600,includes_directory_reservations=True,native_action=False,zip_built=False)))
    try:
        for name in ('prepare_core_publication_v8.py','review_core_publication_v8.py','README_CORE_PUBLICATION_V8.md'):
            raw=read(HERE/name)
            for suffix in ('','.backup','.restore'):put(name+suffix,raw)
        for name,pin in PUBLICATION_V3_PINS.items():
            raw=read(HERE/name)
            if sha(raw)!=pin:raise ValueError('Immutable publicationV3 source differs: '+name)
            for suffix in ('','.backup','.restore'):put('PARENT_V3_'+name+suffix,raw)
        for name,pin in PUBLICATION_V4_PINS.items():
            raw=read(HERE/name)
            if sha(raw)!=pin:raise ValueError('Immutable publicationV4 source differs: '+name)
            for suffix in ('','.backup','.restore'):put('PARENT_V4_'+name+suffix,raw)
        for name,pin in PUBLICATION_V5_PINS.items():
            raw=read(HERE/name)
            if sha(raw)!=pin:raise ValueError('Immutable publicationV5 source differs: '+name)
            for suffix in ('','.backup','.restore'):put('PARENT_V5_'+name+suffix,raw)
        for name,pin in PUBLICATION_V6_PINS.items():
            raw=read(HERE/name)
            if sha(raw)!=pin:raise ValueError('Held publicationV6 draft changed: '+name)
            for suffix in ('','.backup','.restore'):put('PARENT_V6_'+name+suffix,raw)
        for name,pin in PUBLICATION_V7_PINS.items():
            raw=read(HERE/name)
            if sha(raw)!=pin:raise ValueError('Frozen publicationV7 source differs: '+name)
            for suffix in ('','.backup','.restore'):put('PARENT_V7_'+name+suffix,raw)
        verify_handoff_adapter()
        parent_raw=read(HERE/'prepare_core_publication_v2.py')
        if sha(parent_raw)!=PARENT_PROPOSER_SHA or sha(read(FINAL_BUILDER))!=FINAL_BUILDER_SHA:
            raise ValueError('Immutable publicationV2/exact final archive-builder pins required')
        for suffix in ('','.backup','.restore'):put('PARENT_PROPOSER.py'+suffix,parent_raw)
        for name,pin in (('review_core_publication_v2.py',PARENT_REVIEWER_SHA),
                         ('README_CORE_PUBLICATION_V2.md',PARENT_README_SHA)):
            body=read(HERE/name)
            if sha(body)!=pin:raise ValueError('Immutable publicationV2 parent differs: '+name)
            for suffix in ('','.backup','.restore'):put('PARENT_'+name+suffix,body)
        parent_source,middle_source,approved_source=verify_frozen_sources()
        historical33=verify_historical33()
        historical34=verify_historical34()
        verify_named_controls()
        current=verify_current(args)
        current_paths=mirror_current(current,args.current_package)
        put('CURRENT_SOURCE_SELECTION.txt',read(args.current_members_file))
        put('CURRENT_SOURCE_MAP.json',encoded(current))
        frozen=approved_source['replacement_pins']
        summary=args.results_summary
        if summary.resolve(strict=True)!=(HERE/'CORE_REPAIR_RESULTS.md').resolve(strict=True):
            raise ValueError('Final results must be exact canonical CORE_REPAIR_RESULTS.md')
        summary_raw=read(summary)
        if sha(summary_raw)!=args.results_summary_sha256:raise ValueError('Final aggregate results summary differs from supplied pin')
        summary_member=summary.resolve(strict=True).relative_to(ROOT).as_posix()
        base_raw=read(BASE,1024**2)
        if sha(base_raw)!=BASE_SHA:raise ValueError('Exact immutable approved build28 handoff plan required')
        base=strict(base_raw)
        if base.get('schema')!='just-peachy.reviewed-public-handoff.v1' or base.get('reviewed_publication') is not True:raise ValueError('Prior reviewed plan required')
        sources={row['member']:Path(row['source']) for row in base['files']};old={row['member']:row for row in base['files']}
        if len(old)!=697 or len(old)!=len(base['files']):raise ValueError('Exact 697 unique approved build28 sources required')
        sources[C+'START_HERE.md']=ROOT/(C+'START_HERE_CURRENT.md')
        sources[summary_member]=summary
        for path in current_paths:sources[path.relative_to(ROOT).as_posix()]=path
        for name in SUBTREE_SOURCES:
            path=HERE.joinpath(*PurePosixPath(name).parts)
            raw=read(path);raw.decode('utf-8')
            sources[path.relative_to(ROOT).as_posix()]=path
        for name in args.extra_source:
            path=extra_source_path(name)
            raw=read(path);raw.decode('utf-8')
            sources[path.relative_to(ROOT).as_posix()]=path
        queue=list(SELECTED);chosen=set();referenced_history=[];missing_links=[]
        while queue:
            name=queue.pop()
            canonical=(HERE/name).resolve(strict=True)
            if canonical.parent!=HERE.resolve(strict=True):raise ValueError('Same-parent stabilization dependency required')
            name=canonical.name
            if name in chosen:continue
            if re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]*\.(?:py|md)',name) is None:raise ValueError('Explicit flat core source required')
            raw=read(HERE/name);text=raw.decode('utf-8');chosen.add(name)
            for dependency in re.findall(r'\b([A-Za-z][A-Za-z0-9_.-]*\.(?:py|md))\b',text):
                if dependency not in chosen and (HERE/dependency).is_file():
                    queue.append(dependency)
                    if dependency not in SELECTED:referenced_history.append(dependency)
            if name.endswith('.md'):
                for target in re.findall(r'\]\(([^)]+)\)',text):
                    target=target.split('#',1)[0].strip('<>')
                    if not target or ':' in target or target.startswith('/'):continue
                    candidate=(HERE/target).resolve()
                    if candidate.is_relative_to(ROOT) and candidate.is_file():
                        member=candidate.relative_to(ROOT).as_posix()
                        if member not in sources and candidate.parent!=HERE:missing_links.append(member)
                    elif not candidate.is_file():missing_links.append(name+' -> '+target)
        for name in chosen:sources[(HERE/name).relative_to(ROOT).as_posix()]=HERE/name
        for name in NAMED_SHELL_SOURCES:
            raw=read(HERE/name)
            if sha(raw)!=NAMED_SHELL_PINS[name]:raise ValueError('Exact named generic verifier required')
            sources[(HERE/name).relative_to(ROOT).as_posix()]=HERE/name
        for name in NAMED_CONTROL_PINS:
            sources[(HERE/name).relative_to(ROOT).as_posix()]=HERE/name
        for name in CROSS_SOURCES:sources[L+name]=ROOT/(L+name)
        for name in TRACKED:sources[name]=ROOT/name
        rows=[];total=0;aliases=set();changed=[];snapshots={};backed_inputs={}
        for member,path in sorted(sources.items()):
            rel=PurePosixPath(member)
            if (rel.is_absolute() or '..' in rel.parts or '\\' in member or rel.as_posix()!=member
                or member.casefold() in aliases or (path.suffix.lower() not in {'.md','.json','.py','.txt','.toml','.h','.cpp','.c','.sh'}
                    and member not in {(HERE/name).relative_to(ROOT).as_posix() for name in NAMED_SHELL_SOURCES})):
                raise ValueError('Exact unique public source member required')
            aliases.add(member.casefold());relative=path.resolve(strict=True).relative_to(ROOT).as_posix()
            if relative!=member and (member,relative)!=(C+'START_HERE.md',C+'START_HERE_CURRENT.md'):raise ValueError('Only locked StartHere alias permitted: '+member+' -> '+relative)
            raw=read(path);raw.decode('utf-8');total+=len(raw)
            if total>20*1024**2 or len(rows)>=4096:raise ValueError('Original20MiB/4096source bounds')
            row=dict(member=member,source=str(path),bytes=len(raw),sha256=sha(raw));rows.append(row);snapshots[member]=row
            if member not in old or (row['bytes'],row['sha256'])!=(old[member]['bytes'],old[member]['sha256']):
                changed.append(member)
                if relative in backed_inputs:
                    if backed_inputs[relative]!=sha(raw):raise ValueError('Aliased real input changed between archive members')
                else:
                    for prefix in ('source','backup','restore'):put(prefix+'/'+relative,raw)
                    backed_inputs[relative]=sha(raw)
        plan=dict(schema=base['schema'],reviewed_publication=False,
            scope='Final build35 selected source mirror, preserving all approved697 baseline paths and immutable29/30/31/33/34 historical sources. The source mirror and its SOURCE_MAP.md identify the actual current package and separate deployment installer. This conditional source-only plan excludes the complete deployment bundle, private receipts and data. Final observed outcomes and limits are in '+summary_member+'. Failed hour01/hour05/hour06, failed Live51 and all historical evidence retain their original scope; HOST19 does not qualify native first-Start, normalGUI or sustained behavior.',files=rows)
        plan_raw=encoded(plan)
        for suffix in ('','.backup','.restore'):put('PROPOSED_PLAN_REQUIRES_FINAL_REVIEW.json'+suffix,plan_raw)
        if not set(old)<=set(sources):raise ValueError('Every approved build28 handoff member must remain')
        git_names=sorted(set(TRACKED)|{(HERE/name).relative_to(ROOT).as_posix() for name in chosen}|
            {L+name for name in CROSS_SOURCES}|{summary_member}|
            {(HERE.joinpath(*PurePosixPath(name).parts)).relative_to(ROOT).as_posix() for name in SUBTREE_SOURCES}|
            {extra_source_path(name).relative_to(ROOT).as_posix() for name in args.extra_source}|
            {path.relative_to(ROOT).as_posix() for path in current_paths})
        git_names=sorted(set(git_names)|{(HERE/name).relative_to(ROOT).as_posix() for name in NAMED_SHELL_SOURCES})
        git_names=sorted(set(git_names)|{(HERE/name).relative_to(ROOT).as_posix() for name in NAMED_CONTROL_PINS})
        put('GIT_WHITELIST.txt',('\n'.join(git_names)+'\n').encode())
        if any(sha(read(path))!=snapshots[member]['sha256'] for member,path in sources.items()):raise ValueError('Publication source changed after backup')
        result=dict(output=str(out),base_plan_sha256=BASE_SHA,
            selected_runtime_manifest_sha256=args.current_manifest_sha256,
            current_build=35,current_source_map=current,current_source_map_sha256=sha(encoded(current)),
            current_source_map_member=(CURRENT_MIRROR/'SOURCE_MAP.md').relative_to(ROOT).as_posix(),
            current_source_mirror_members=[path.relative_to(ROOT).as_posix() for path in current_paths],
            source_mirror_independent_readbacks=True,source_mirror_maximum_bytes=8*1024**2,
            frozen_build31_manifest_sha256=PIN,
            frozen_build31_source_review_sha256=SOURCE_REVIEW_SHA,frozen_replacements=len(frozen),
            frozen_source_inputs=len(approved_source['source_pins']),
            frozen_middle_build30_source_review_sha256=MIDDLE_SOURCE_REVIEW_SHA,
            frozen_middle_build30_source_inputs=len(middle_source['source_pins']),
            frozen_middle_build30_replacements=len(middle_source['replacement_pins']),
            frozen_parent_build29_source_review_sha256=PARENT_SOURCE_REVIEW_SHA,
            frozen_parent_build29_source_inputs=len(parent_source['source_pins']),
            frozen_parent_build29_replacements=len(parent_source['replacement_pins']),
            immutable_build31_candidate_content_sha256=PACKAGE_CONTENT_SHA,
            frozen_build33_manifest_sha256=HISTORICAL33_PIN,
            frozen_build33_source_review_sha256=HISTORICAL33_SOURCE_REVIEW_SHA,
            frozen_build33_source_inputs=len(historical33['source_pins']),
            frozen_build33_replacements=len(historical33['replacement_pins']),
            frozen_build34_manifest_sha256=HISTORICAL34_PINS['manifest'],
            frozen_build34_source_review_sha256=HISTORICAL34_PINS['source_review'],
            frozen_build34_source_inputs=len(historical34['source_pins']),
            frozen_build34_replacements=len(historical34['replacement_pins']),
            selected_named_control_sources=list(NAMED_CONTROL_PINS),
            selected_named_shell_sources=list(NAMED_SHELL_SOURCES),
            selected_explicit_subtree_sources=list(SUBTREE_SOURCES),
            selected_canonical_guides=list(GUIDE_TARGETS),selected_existing_entries=list(ENTRY_TARGETS),
            selected_extra_sources=list(args.extra_source),
            final_archive_builder_sha256=FINAL_BUILDER_SHA,
            final_archive_adapter_sha256=HANDOFF_ADAPTER_SHA,
            results_summary_member=summary_member,results_summary_sha256=args.results_summary_sha256,
            prior_members=len(old),members=len(rows),source_bytes=total,git_publication_members=len(git_names),
            selected_stabilization_files=sorted(chosen),referenced_historical_sources=sorted(set(referenced_history)),
            changed_existing_and_new_members=changed,unresolved_current_links=sorted(set(missing_links)),
            proposed_plan_sha256=sha(plan_raw),reviewed_publication=False,native_action=False,zip_built=False,
            independent_changed_source_restores=True,backed_real_inputs=len(backed_inputs),duplicate_archive_aliases_use_same_exact_restored_input=True,private_media_models_galleries_included=False,
            all_approved_build28_member_paths_preserved=True,
            unchanged_sources_reuse_prior_closed_backups=True,
            directory_reserved_bytes=len(directories)*65536,prepared_allocated_bytes=written)
        put('PLAN_REVIEW.json',encoded(result));put('SOURCE_CLOSED.json',encoded(dict(closed_unix=time.time(),prepared_allocated_bytes=written,source_backups_and_independent_restores=True,native_action=False)))
        print(json.dumps(dict(output=str(out),members=len(rows),source_bytes=total,git_publication_members=len(git_names),unresolved_current_links=result['unresolved_current_links'],reviewed_publication=False,zip_built=False)))
    except BaseException as error:
        put('FAILURE.json',encoded(dict(type=type(error).__name__,message=str(error)[:2048])));raise

if __name__=='__main__':main()
