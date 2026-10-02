# Current runtime progress

field-runtime-v27 is installed, idle and capture off, display270, with three
recording slots remaining and ten profile shortcuts plus rollback. The shared
mounted BMI270 implementation and array-centered transform are deployed.

Actual changed integration:5.25s/84000samples/525blocks;79causal beam records with
no queue drops;44pose records, including8explicit invalid startup poses and36valid
poses after automatic stationary recovery. Source/model/archive/command closure,
local backup and two complete independent PC copies passed. IMU thread50.29Hz,
1.21% of one core. The same final code's optional graphic show/tap/hide passed.

All ten profiles bind the exact common capsule. Earlier model/raw/control passes
remain separately scoped; unchanged profiles were not exhaustively rerun. Old
v25/v26 failures remain preserved. Current receipts are MOTION_RELEASE_INDEX,
MOTION_CHECKLIST and MOTION_HANDOFF_RECEIPT. Old FINAL_* receipts describe v23.

No additional native job is required for this handoff. Physical touch, cable-
disconnected coldboot, long-term yaw drift, battery endurance and noisy-human
recognition remain operator validation. Reliable inertial room position is not
available; acceleration suspends location priors without inventing translation.
