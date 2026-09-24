"""Independent analytic 3D trajectories; run commands in app/README_IMU.md."""
import math
import unittest
from app.imu import RelativeMotion, mounted_array_motion
from types import SimpleNamespace
from app.inertial_geometry import (GRAVITY, MountGeometry, dot, horizontal_candidates,
    matvec, norm, rotate, specific_force_at_array)

MOUNT = dict(sensor_to_device=[[0,1,0],[-1,0,0],[0,0,1]],
             array_zero_axis_device=[1,0,0], axes_verified=True,
             sensor_position_from_array_m=[-.07,-.09,-.05], offset_verified=True)
BIAS = (.1,-.2,.3)
IDENTITY = ((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))
def transpose(matrix): return tuple(zip(*matrix))
def mm(a,b): return tuple(tuple(dot(row,col) for col in transpose(b)) for row in a)

def rodrigues(rate, dt):
    """Independent matrix ground truth, not production quaternions."""
    magnitude=norm(rate)
    if not magnitude:return IDENTITY
    x,y,z=(v/magnitude for v in rate)
    c=math.cos(math.radians(magnitude*dt)); s=math.sin(math.radians(magnitude*dt)); v=1-c
    return ((c+x*x*v,x*y*v-z*s,x*z*v+y*s),
            (y*x*v+z*s,c+y*y*v,y*z*v-x*s),
            (z*x*v-y*s,z*y*v+x*s,c+z*z*v))

class IMUTests(unittest.TestCase):
    def test_unassembled_sensor_never_modifies_array_directions(self):
        worker=SimpleNamespace(motion=RelativeMotion(fixed_mount=False,compensate=True,mount=MOUNT))
        self.assertIsNone(mounted_array_motion(worker,'live'))
        worker.motion.fixed_mount=True
        self.assertIs(mounted_array_motion(worker,'live'),worker)
        self.assertIsNone(mounted_array_motion(worker,'file'))
        unavailable=object()
        self.assertIs(mounted_array_motion(unavailable,'live'),unavailable)

    def sample(self,m,acc,rate,dt=.02):
        inverse=transpose(m.mount.rotation)
        gyro=tuple(x+y for x,y in zip(matvec(inverse,rate),BIAS))
        return m.update((m.last+dt) if m.last is not None else 0.,matvec(inverse,acc),gyro)

    def calibrated(self,up=(0.,0.,1.),compensate=True):
        # These analytic attitude trajectories rotate about the sensor itself;
        # test lever-arm acceleration separately with the appropriate forces.
        m=RelativeMotion(fixed_mount=True,compensate=compensate,mount={**MOUNT,'offset_verified':False})
        for _ in range(110):self.sample(m,up,(0.,0.,0.))
        self.assertTrue(m.valid)
        return m

    def segment(self,m,matrix,rate,steps,up=(0.,0.,1.)):
        for _ in range(steps):
            matrix=mm(matrix,rodrigues(rate,.02))
            self.sample(m,matvec(transpose(matrix),up),rate)
        return matrix

    def test_user_mount_and_positive_yaw_sign(self):
        mount=MountGeometry(MOUNT)
        self.assertEqual(mount.map((1,0,0)),(0,-1,0))
        self.assertEqual(mount.map((0,1,0)),(1,0,0))
        self.assertEqual(mount.map((0,0,1)),(0,0,1))
        for up in ((0.,0.,1.),(0.,1.,0.)):
            m=self.calibrated(up)
            self.segment(m,IDENTITY,tuple(20*x for x in up),50,up)
            self.assertAlmostEqual(m.yaw,20.,places=6)
            self.assertAlmostEqual(m.transform(70.,m.last)[0],90.,places=6)

    def test_flat_to_portrait_and_back_preserves_horizontal_bearing(self):
        m=self.calibrated(); generation=m.frame_generation
        matrix=self.segment(m,IDENTITY,(30.,0.,0.),150)
        self.assertTrue(m.valid);self.assertAlmostEqual(m.yaw,0.,places=6)
        self.assertAlmostEqual(m.transform(60.,m.last)[0],60.,places=6)
        self.segment(m,matrix,(-30.,0.,0.),150)
        self.assertAlmostEqual(m.yaw,0.,places=6)
        self.assertEqual(m.frame_generation,generation);self.assertEqual(m.unsafe_generation,0)

    def test_turn_after_lift_uses_new_gravity_axis_both_signs(self):
        for direction in (-1,1):
            m=self.calibrated();matrix=self.segment(m,IDENTITY,(30.,0.,0.),150)
            self.segment(m,matrix,(0.,direction*20.,0.),50)
            self.assertAlmostEqual(m.yaw,direction*20.,places=6)
            self.assertAlmostEqual(m.transform(90.-direction*20.,m.last)[0],90.,places=6)
            self.assertTrue(m.valid)

    def test_compound_rotation_matches_independent_matrix(self):
        m=self.calibrated();matrix=self.segment(m,IDENTITY,(9.,12.,20.),100)
        for vector in IDENTITY:
            self.assertLess(norm(tuple(a-b for a,b in zip(rotate(m.q,vector),matvec(matrix,vector)))),1e-6)
        self.assertAlmostEqual(norm(m.q),1.,places=10)

    def test_tilted_array_intersection_is_not_just_adding_yaw(self):
        native=math.degrees(math.acos(math.cos(math.radians(30))*math.cos(math.radians(60))))
        candidates=horizontal_candidates(native,(math.cos(math.radians(30)),0.))
        self.assertAlmostEqual(candidates[0],60.,places=6)
        self.assertAlmostEqual(candidates[1],-60.,places=6)
        self.assertEqual(horizontal_candidates(10.,(.5,0.)),())
        self.assertEqual(horizontal_candidates(90.,(.01,0.)),())

    def test_vertical_array_recovers_without_reference_reset(self):
        m=self.calibrated();generation=m.frame_generation
        matrix=self.segment(m,IDENTITY,(0.,30.,0.),150)
        self.assertFalse(m.valid);self.assertEqual(m.transform(90.,m.last),(None,0.))
        self.segment(m,matrix,(0.,-30.,0.),150)
        self.assertTrue(m.valid);self.assertEqual(m.frame_generation,generation)

    def test_repeated_turns_and_more_than_thirty_seconds_do_not_latch(self):
        m=self.calibrated();self.segment(m,IDENTITY,(0.,0.,20.),1800)
        self.assertTrue(m.valid);self.assertAlmostEqual(m.yaw,720.,places=5)
        self.assertAlmostEqual(m.transform(90.,m.last)[0],90.,places=5)
        self.assertGreater(m.moving_seconds,30.)

    def test_acceleration_retains_heading_then_automatically_resumes(self):
        m=self.calibrated();generation=m.frame_generation
        self.sample(m,(.4,0.,1.),(0.,0.,0.))
        self.assertFalse(m.valid);self.assertEqual(m.unsafe_generation,1)
        for _ in range(60):self.sample(m,(0.,0.,1.),(0.,0.,0.))
        self.assertTrue(m.valid);self.assertEqual(m.frame_generation,generation)
        self.assertAlmostEqual(m.yaw,0.,places=6)

    def test_gap_and_clipping_automatically_start_new_frame(self):
        for dt,rate in ((.2,(0.,0.,0.)),(.02,(0.,0.,499.))):
            m=self.calibrated();old_at=m.last;generation=m.frame_generation
            self.sample(m,(0.,0.,1.),rate,dt)
            self.assertFalse(m.valid);self.assertEqual(m.transform(90.,old_at),(None,0.))
            for _ in range(110):self.sample(m,(0.,0.,1.),(0.,0.,0.))
            self.assertTrue(m.valid);self.assertEqual(m.frame_generation,generation+1)
            self.assertEqual(m.transform(90.,old_at),(None,0.))

    def test_invalid_and_stale_data_cannot_supply_direction(self):
        m=self.calibrated()
        self.assertEqual(m.transform(90.,m.last+.3),(None,0.))
        self.assertEqual(m.transform(90.,-1.),(None,0.))
        with self.assertRaises(ValueError):m.update(m.last,(0.,0.,1.),BIAS)
        with self.assertRaises(ValueError):m.update(m.last+.02,(math.nan,0.,1.),BIAS)

    def test_native_fold_ambiguity_rejected_never_clamped(self):
        m=self.calibrated();self.segment(m,IDENTITY,(0.,0.,20.),50)
        self.assertEqual(m.transform(10.,m.last),(None,0.))
        self.assertEqual(m.transform(179.,m.last),(None,0.))

    def test_boot_reference_is_fresh_not_persisted(self):
        m=self.calibrated();self.segment(m,IDENTITY,(0.,0.,20.),50)
        fresh=self.calibrated();self.assertEqual(fresh.yaw,0.);self.assertEqual(fresh.frame_generation,1)

    def test_unverified_or_invalid_mount(self):
        m=RelativeMotion(fixed_mount=True,compensate=True)
        for i in range(110):m.update(i*.02,(0.,0.,1.),BIAS)
        self.assertFalse(m.valid);self.assertIn('alignment pending',m.reason)
        for override in (dict(sensor_to_device=[[-1,0,0],[0,1,0],[0,0,1]]),
                         dict(array_zero_axis_device=[2,0,0]),dict(axes_verified='yes'),
                         dict(sensor_position_from_array_m=[math.nan,0,0])):
            with self.assertRaises(ValueError):MountGeometry({**MOUNT,**override})

    def test_disabled_compensation_reanchors_after_turn(self):
        m=self.calibrated(compensate=False)
        self.assertEqual(m.transform(90.,m.last),(90.,1.))
        self.sample(m,(0.,0.,1.),(0.,0.,20.));self.assertFalse(m.valid)
        for _ in range(110):self.sample(m,(0.,0.,1.),(0.,0.,0.))
        self.assertTrue(m.valid);self.assertEqual(m.frame_generation,2)

    def test_lever_arm_tangential_and_centripetal_signs(self):
        # Sensor -> center=(.07,.09,.05). alpha x r=(-.27,.21,0), w x w x r=(-.28,-.36,0).
        force=specific_force_at_array((0.,0.,1.),(0.,0.,2.),(0.,0.,3.),(-.07,-.09,-.05))
        self.assertAlmostEqual(force[0],-.55/GRAVITY);self.assertAlmostEqual(force[1],-.15/GRAVITY)
        self.assertEqual(force[2],1.)
        self.assertEqual(specific_force_at_array((0.,0.,1.),(0.,0.,2.),(0.,0.,3.),(0.,0.,0.)),(0.,0.,1.))

if __name__=='__main__':unittest.main()
