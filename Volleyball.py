from ursina import *
from ursina.shaders.colored_lights_shader import colored_lights_shader

import random

app = Ursina()
player_score = 0
ai_score = 0
player_touches = 0
ai_touches = 0
player_team_touches = 0
ai_team_touches = 0


Sky()

# Court boundaries
COURT_X_MIN = -15
COURT_X_MAX = 15
opp_spike = False

last_hitter = None  # "player" or "ai"

score_text = Text("0    -    0", origin=(0,0), y=.45, scale=2)
sound = Audio('audio/bump.mp3', loop=False, autoplay=False)
spike = Audio('audio/spike.mp3', loop=False, autoplay=False)
crowd = Audio('audio/crowd.mp3', loop=True, auto_play=True)
clap = Audio('audio/clap.mp3', loop=False, autoplay=False)
# --------------------------------------------------
# VISUAL EFFECTS
# --------------------------------------------------

def bump_effect(position, color=color.white):
    """Small bump explosion."""
    e = Entity(
        model='sphere',
        position=position,
        scale=.2,
        color=color,
        emissive=True
    )
    e.animate_scale(1, duration=0.15)
    sound.play()
    destroy(e, delay=0.25)

def spike_effect(position):
    """Big shockwave for strong attacks."""
    wave = Entity(
        model='circle',
        position=position,
        scale=0.5,
        rotation_x=90,
        color=color.red,
        emissive=True
    )
    wave.animate_scale(4, duration=0.25, curve=curve.out_expo)
    wave.animate_color(color.clear, duration=0.25)
    destroy(wave, delay=0.3)

    # Bright flash on ball
    flash = Entity(
        model='sphere',
        position=position,  
        scale=0.5,
        color=color.rgb(255,80,80),
        emissive=True
    )
    flash.animate_color(color.clear, duration=0.15)
    spike.play()
    destroy(flash, delay=0.2)


def camera_shake(intensity=.4, duration=0.2):
    """Quick punch shake."""
    original_pos = camera.position

    def do_shake():
        camera.position = original_pos + Vec3(
            random.uniform(-intensity,intensity),
            random.uniform(-intensity,intensity),
            0
        )

    invoke(do_shake, delay=0)
    invoke(lambda: setattr(camera, "position", original_pos), delay=duration)


# -------------------------------------------
# ENVIRONMENT
# -------------------------------------------

ground = Entity(model='cube', texture='white_cube', scale=(30,1,20), collider='box', color=color.light_gray,shader=colored_lights_shader)
ground.visible=False
groundLayer = Entity(model='models/court', scale=2, shader=colored_lights_shader,position=(0,1.1,0))
groundLayer.rotation=(0,90,0)
groundLayer.visible=True
out = Entity(model='cube', texture='grass', scale=(80,1,80), collider='box', color=color.rgb(0,255,0),shader=colored_lights_shader)
out.visible=False
net = Entity(model='cube', color=color.rgb(150,150,150), scale=(0.2,8,20), position=(0,2,0), collider='box',shader=colored_lights_shader)
net.visible=False
park=Entity(model='models/park',scale=4,position=(-10,-5,50), shader=colored_lights_shader)
park.visible=False
stadium=Entity(model='models/stadium', scale=.5, position=(0,-2,0), shader=colored_lights_shader)
stadium.rotation=(0,90,0)
stadium.visible=False
# -------------------------------------------
# BALL
# -------------------------------------------

ball_model=Entity(model='models/volleyball',scale=.02)
ball = Entity(
    model = 'sphere',
    scale=1,
    position=(0,10,0),
    collider='sphere'
)
ball.velocity = Vec3(0,0,0)
ball.angular_velocity = Vec3(0,0,0)
ball_model.parent=ball
GRAVITY = 0.15

# -------------------------------------------
# BALL TRAJECTORY VISUALIZATION
# -------------------------------------------

trajectory_points = []
TRAJECTORY_LENGTH = 20
TRAJECTORY_STEP = 0.8

# Create visual trajectory markers
for i in range(TRAJECTORY_LENGTH):
    p = Entity(model='sphere', scale=.15, color=color.yellow, enabled=False)
    trajectory_points.append(p)


def predict_trajectory():
    """Simulate ball path forward without modifying real ball."""
    points = []

    sim_pos = Vec3(ball.position)
    sim_vel = Vec3(ball.velocity)

    for i in range(TRAJECTORY_LENGTH):

        # Apply gravity
        sim_vel.y -= GRAVITY * TRAJECTORY_STEP

        # Move
        sim_pos += sim_vel * TRAJECTORY_STEP

        # Ground bounce
        if sim_pos.y < 0.1:
            sim_pos.y = 0.5
            sim_vel.y *= -0.6

        # Net collision
        if abs(sim_pos.x - net.x) < 0.3 and sim_pos.y <= net.y + net.scale_y/2:
            sim_vel.x *= -0.5

        points.append(Vec3(sim_pos))

    return points

def play_bump_animation(player):
    # forward bump push
    player.arm_left.animate_position((-0.25, -0.25, 0.4), duration=0.08, curve=curve.linear)
    player.arm_right.animate_position((0.25, -0.25, 0.4), duration=0.08, curve=curve.linear)

    # slight dip
    invoke(
        lambda: [
            player.arm_left.animate_position((-0.25, -0.55, 0.6), duration=0.1, curve=curve.linear),
            player.arm_right.animate_position((0.25, -0.55, 0.6), duration=0.1, curve=curve.linear)
        ],
        delay=0.08
    )

    # return to idle
    invoke(
        lambda: [
            player.arm_left.animate_position((-.75,-.6,-1), duration=0.12, curve=curve.out_expo),
            player.arm_right.animate_position((.75,-.6,1), duration=0.12, curve=curve.out_expo)
        ],
        delay=0.18
    )

def play_spike_animation(player):
    # forward bump push
    player.arm_right.animate_position((0.55, 1, 0.4), duration=0.2, curve=curve.linear)
    # slight dip
    invoke(
        lambda: [
            player.arm_right.animate_position((0.25, -0.55, 0.6), duration=0.1, curve=curve.linear),
            player.arm_right.animate_rotation((0,-90,-45), duration=0.2, curve=curve.linear)
        ],
        delay=0.3
    )

    # return to idle
    invoke(
        lambda: [
            player.arm_right.animate_position((.75,-.6,1), duration=0.12, curve=curve.out_expo),
            player.arm_right.animate_rotation((0,45,-45), duration=0.08, curve=curve.out_expo)
        ],
        delay=0.6
    )

class Teammate(Entity):
    def __init__(self, position=(0,1,0), is_player=True):
        super().__init__(
            model='cube',
            color=color.azure if is_player else color.orange,
            scale=(1,2,1),
            position=position,
            collider='box'
        )
        self.is_player = is_player
        self.speed = 5
        self.hit_zone = Entity(
            parent=self,
            model='cube',
            scale=(1,1,1.5),
            position=(0,1,-1),
            color=color.rgba(255,255,255,40),
            collider='box'
        )
        self.has_hit = False   # Track if they already touched the ball in current rally
        self.freeze = False    # Used to freeze after receiving

    def update_ai(self):
        # AI teammate only moves to receive the ball if it's on their side
        if serve_mode or self.freeze:
            return

        if ball.x > 0:  # AI side
            target_x = ball.x
            target_z = ball.z
            # Stay on AI side only
            if target_x < 0:
                target_x = 0
            # Move toward predicted position
            self.position += Vec3(
                (target_x - self.x) * self.speed * time.dt,
                0,
                (target_z - self.z) * self.speed * time.dt
            )

        # Hit the ball only if it hasn't been hit yet and on own side
        if self.hit_zone.intersects(ball).hit and not self.has_hit and ball.x > 0:
            self.receive_ball()

    def receive_ball(self):
        global last_hitter, player_team_touches
        if self.has_hit:
            return  # Already touched this rally

        player_team_touches += 1
        self.has_hit = True
        last_hitter = "player"

        # Decide bump direction based on team touch number
        if player_team_touches == 1:
            # First touch → receive, just lift the ball up
            target_pos = player.position + Vec3(0,1,0)
        elif player_team_touches == 2:
            # Second touch → set toward spiker (player)
            target_pos = player.position + Vec3(0,1,0)
        else:
            # Third touch → attack over the net (opponent side)
            target_pos = Vec3(random.uniform(5,10),1,random.uniform(-3,3))

        bump_dir = (target_pos - self.position).normalized()
        bump_dir.y += 0.5  # add lift
        ball.velocity = bump_dir * 12

        bump_effect(self.position)
        ball.angular_velocity = Vec3(
            random.uniform(-200,200),
            random.uniform(-200,200),
            random.uniform(-200,200)
        )

        self.freeze = True  # freeze after hitting


class PlayerTeammate(Teammate):
    def update(self):
        if serve_mode:
            return

        # --- Always chase the ball if it's on player side ---
        if ball.x < 0:
            target_pos = Vec3(ball.x, self.y, ball.z)
            move_dir = target_pos - self.position
            if move_dir.length() > 0.1:
                self.position += move_dir.normalized() * self.speed * time.dt

        # --- Hit the ball if in range and haven't hit yet ---
        if not self.has_hit:
            distance_to_ball = (ball.position - self.position).length()
            if distance_to_ball < 1.5:  # slightly bigger than hit_zone
                self.receive_ball()

    def receive_ball(self):
        global last_hitter, player_team_touches
        if self.has_hit:
            return

        player_team_touches += 1
        self.has_hit = True
        last_hitter = "player"

        # Determine target
        if player_team_touches == 1:
            # First touch → just lift
            target_pos = self.position + Vec3(0,3,0)
        elif player_team_touches == 2:
            # Second touch → set toward opponent side over net
            target_pos = self.position + Vec3(0,3,0)
        else:
            # Third touch → attack toward opponent court
            target_pos = Vec3(random.uniform(5,10),1,random.uniform(-3,3))

        # Apply bump
        bump_dir = (target_pos - self.position).normalized()
        bump_dir.y += 0.5
        ball.velocity = bump_dir * 12

        bump_effect(self.position)
        ball.angular_velocity = Vec3(
            random.uniform(-200,200),
            random.uniform(-200,200),
            random.uniform(-200,200)
        )

        # Freeze after first touch
        if player_team_touches == 1:
            self.freeze = True

# -------------------------------------------
# PLAYER
# -------------------------------------------

class Player(Entity):
    def __init__(self, position=(-10,1,0)):
        super().__init__(visible=False)

        self.position = Vec3(*position)
        self.speed = 10
        self.jump_force = 0.35
        self.vy = 0
        self.on_ground = True
        self.mouse_sensitivity = 80
        self.hit_cooldown = 0      # Time remaining until next allowed hit
        self.cooldown_duration = 0.2  # 0.2 seconds between hits


        # First-person camera
        self.camera = Entity(parent=self, position=(0,1.7,0))
        camera.parent = self.camera
        camera.fov = 95
        camera.position = (0,0,0)
        camera.rotation = (0,0,0)

        mouse.locked = True

        # Hit zone in front of camera
        self.hit_zone = Entity(
            parent=camera,
            model='cube',
            scale=(0.5,0.5,2),
            position=(0,0,1.5),
            color=color.rgba(255,255,255,40),
            collider='box'
        )
        
        # -----------------------------------------
#  First-Person Volleyball Arms
# -----------------------------------------

        # in Player.__init__ after camera setup
        # First-person arms
        self.arm_left = Entity(
            model='cube',
            texture='white_cube',
            color=color.rgb(255,229,180),
            position=Vec3(-.75,-.6,-1),
            rotation=Vec3(0,-45,45),
            parent=camera.ui,
            scale=(.3,.5,.3),
            visible=True
        )
        self.arm_right = Entity(
            model='cube',
            texture='white_cube',
            color=color.rgb(255,229,180),
            position=Vec3(.75,-.6,1),
            rotation=Vec3(45,-45,0),
            parent=camera.ui,
            scale=(.3,.5,.3),
            visible=True
        )


    def update(self):
        global serve_mode
        # Reduce cooldown timer
        if self.hit_cooldown > 0:
            self.hit_cooldown -= time.dt


        if serve_mode:
            return

        # ----- MOUSE LOOK -----
        camera.rotation_x -= mouse.velocity[1] * self.mouse_sensitivity
        self.rotation_y += mouse.velocity[0] * self.mouse_sensitivity
        camera.rotation_x = clamp(camera.rotation_x, -80, 80)

        # ----- MOVEMENT -----
        forward = self.forward * (held_keys['w'] - held_keys['s'])
        right   = self.right   * (held_keys['d'] - held_keys['a'])

        move = (forward + right) * self.speed * time.dt
        self.position += Vec3(move.x, 0, move.z)

        # ----- JUMP / GRAVITY -----
        self.vy -= 0.8 * time.dt
        self.y += self.vy

        if self.y <= 1:
            self.y = 1
            self.vy = 0
            self.on_ground = True

        if held_keys['space'] and self.on_ground:
            self.vy = self.jump_force
            self.on_ground = False

    def hit(self):
        global last_hitter, player_touches

        if serve_mode or self.hit_cooldown > 0:
            return

        if self.hit_zone.intersects(ball).hit:
            last_hitter = "player"
            player_touches += 1

            # Reset cooldown
            self.hit_cooldown = self.cooldown_duration

            # Check 3-touch limit
            if player_touches > 3:
                award_point("ai")
                return

            forward_dir = camera.forward + Vec3(0, 1, 0)
            forward_dir = forward_dir.normalized()

            ball.velocity = forward_dir * 12
            bump_effect(ball.position)
            play_bump_animation(self)
            ball.angular_velocity = Vec3(
                random.uniform(-200, 200),
                random.uniform(-200, 200),
                random.uniform(-200, 200)
            )

    def spike(self):
        global last_hitter, player_touches

        if serve_mode or self.hit_cooldown > 0:
            return

        if self.hit_zone.intersects(ball).hit:
            last_hitter = "player"
            player_touches += 1

            # Reset cooldown
            self.hit_cooldown = self.cooldown_duration

            # Check 3-touch limit
            if player_touches > 3:
                award_point("ai")
                return

            forward_dir = camera.forward + Vec3(0, -.5, 0)
            forward_dir = forward_dir.normalized()

            ball.velocity = forward_dir * 15
            spike_effect(self.position)
            camera_shake()
            play_spike_animation(self)
            ball.angular_velocity = Vec3(
                random.uniform(-400, 400),
                random.uniform(-200, 200),
                random.uniform(-150, 150)
            )


player = Player()

# -------------------------------------------
# AI OPPONENT
# -------------------------------------------

class Opponent(Entity):
    def __init__(self, position=(10,1,0)):
        super().__init__(
            model='cube',
            color=color.red,
            scale=(1,2,1),
            position=position,
            collider='box'
        )
        self.speed = 6
        self.hit_cooldown = 0  # Time remaining until next allowed hit
        self.cooldown_duration = 0.5  # Half a second cooldown

        self.hit_zone = Entity(
            parent=self,
            model='cube',
            scale=(1,1,1.5),
            position=(0,1,-1),
            color=color.rgba(255,0,0,40),
            collider='box'
        )

    def update_ai(self):
        if serve_mode:
            return

        # Reduce cooldown timer
        if self.hit_cooldown > 0:
            self.hit_cooldown -= time.dt

        if ball.x > 0:
            predicted_x = ball.x + ball.velocity.x * 0.1
            predicted_z = ball.z + ball.velocity.z * 0.1

            target_x = predicted_x
            target_z = predicted_z

            # Move AI
            if target_x > self.x:
                self.x += self.speed * time.dt
            else:
                self.x -= self.speed * time.dt

            if target_z > self.z:
                self.z += self.speed * time.dt
            else:
                self.z -= self.speed * time.dt

            # Hit ball if cooldown allows
            if self.hit_cooldown <= 0 and self.hit_zone.intersects(ball).hit:
                self.hit_ball()
                self.hit_cooldown = self.cooldown_duration  # Reset cooldown

    def hit_ball(self):
        global opp_spike, last_hitter, ai_touches
        last_hitter = "ai"
        ai_touches += 1

        # Check 3-touch limit
        if ai_touches > 3:
            award_point("player")
            return

        opp_spike = random.choice([False,True])
        if opp_spike:
            bump_dir = Vec3(-1, 1, random.uniform(-0.3, 0.3)).normalized()
            ball.velocity = bump_dir * 13
            spike_effect(self.position)
            camera_shake()
            ball.angular_velocity = Vec3(
                random.uniform(-400, 400),
                random.uniform(-200, 200),
                random.uniform(-150, 150)
            )
        else:
            bump_dir = Vec3(-1, 1.25, random.uniform(-0.3, 0.3)).normalized()
            ball.velocity = bump_dir * 12
            bump_effect(self.position)
            ball.angular_velocity = Vec3(
                random.uniform(-200, 200),
                random.uniform(-200, 200),
                random.uniform(-200, 200)
            )

opponent = Opponent()
player_teammate = PlayerTeammate(position=(-12,1,2))
opponent_teammate = Teammate(position=(12,1,2), is_player=False)
player.has_hit = False
player_teammate.has_hit = False
opponent.has_hit = False
opponent_teammate.has_hit = False


# -------------------------------------------
# SERVING SYSTEM
# -------------------------------------------

serve_mode = True
server = "player"

serve_text = Text("Press E to Serve", origin=(0,0), y=0.4, scale=2)

def reset_for_serve():
    global serve_mode, server, player_touches, ai_touches
    serve_mode = True
    ball.velocity = Vec3(0,0,0)
    player_touches = 0
    ai_touches = 0

    # Reset teammates
    player_teammate.has_hit = False
    player_teammate.freeze = False
    opponent_teammate.has_hit = False
    opponent_teammate.freeze = False

    if server == "player":
        player.position = (-10,1,0)
        player_teammate.position = (-12,1,2)
        ball.position = player.position + Vec3(1,3,0)
        serve_text.text = "Press E to Serve"
    else:
        opponent.position = (10,1,0)
        opponent_teammate.position = (12,1,2)
        ball.position = opponent.position + Vec3(-1,10,0)
        serve_text.text = "AI Serving..."
    serve_text.enabled = True


def do_serve():
    global serve_mode, server
    serve_mode = False
    serve_text.enabled = False

    if server == "player":
        player.position = (-10,1,0)
        ball.velocity = Vec3(0.5,10,random.uniform(-1,1))
    else:
        opponent.position = (10,1,0)
        ball.velocity = Vec3(-0.5,10,random.uniform(-1,1))

def crowd_cheer():
    for c in crowd_entities:
        jump_height = random.uniform(0.3, 0.7)
        c.animate_y(c.y + jump_height, duration=0.2, curve=curve.out_expo)
        c.animate_y(0.5, duration=0.3, delay=0.2, curve=curve.in_expo)


# -------------------------------------------
# INPUT
# -------------------------------------------

def input(key):
    if key == 'left mouse down':
        if player.on_ground:
            player.hit()
        else:
            player.spike()
    if key == 'e' and serve_mode and server == "player":
        do_serve()

# -------------------------------------------
# SCORING
# -------------------------------------------

def award_point(to):
    global player_score, ai_score, server, player_team_touches, ai_team_touches
    if to == "player":
        player_score += 1
        server = "player"
    else:
        ai_score += 1
        server = "ai"

    player_team_touches = 0
    ai_team_touches = 0

    clap.play()
    score_text.text = f"{player_score}    -    {ai_score}"
    crowd_cheer()
    reset_for_serve()


# -------------------------------
# CROWD SURROUNDING THE COURT
# -------------------------------

crowd_entities = []
CROWD_ROWS = 5
CROWD_COLS = 35
CROWD_SPACING = 1
COURT_X_MIN, COURT_X_MAX = -32, 32
COURT_Z_MIN, COURT_Z_MAX = -30, 30  # approximate court boundaries

for row in range(CROWD_ROWS):
    for col in range(CROWD_COLS):
        # --- Back side (behind player) ---
        x = COURT_X_MIN + col * (COURT_X_MAX - COURT_X_MIN) / (CROWD_COLS - 1) * CROWD_SPACING
        z = COURT_Z_MIN - row * 1.5
        e = Entity(model='cube', scale=(1,5,1),
                   color=color.rgb(random.randint(100,255),random.randint(100,255),random.randint(100,255)),
                   position=(x, 0.5, z), shader=colored_lights_shader)
        e.idle_offset = random.uniform(0, 2*3.1415)
        crowd_entities.append(e)

        # --- Front side (behind AI) ---
        z = COURT_Z_MAX + row * 1.5
        e2 = Entity(model='cube', scale=(1,5,1),
                    color=color.rgb(random.randint(100,255),random.randint(100,255),random.randint(100,255)),
                    position=(x, 0.5, z), shader=colored_lights_shader)
        e2.idle_offset = random.uniform(0, 2*3.1415)
        crowd_entities.append(e2)

# -------------------------------------------
# UPDATE LOOP
# -------------------------------------------

def update():
    global server

    if serve_mode and server == "ai":
        invoke(do_serve, delay=1.2)
        server = "waiting"

    player.update()
    player_teammate.update()
    opponent.update_ai()
    opponent_teammate.update_ai()


    ball.velocity.y -= GRAVITY
    ball.position += ball.velocity * time.dt

    if ball.y < 0.1:
        ball.y = 0.5
        ball.velocity.y *= -0.6

    if ball.intersects(net).hit:
        if ball.y <= net.y + net.scale_y/2:
            ball.velocity.x *= -0.5

    if ball.intersects(ground).hit:
        if ball.x < 0:
            award_point("ai")
        else:
            award_point("player")

    elif ball.intersects(out).hit:
        if last_hitter == "ai":
            award_point("player")
        else:
            award_point("ai")

    # -------------------------------
    # UPDATE TRAJECTORY VISUAL LINE
    # -------------------------------
    future_path = predict_trajectory()
    for i, p in enumerate(trajectory_points):
        p.position = future_path[i]
        p.enabled = True

    # apply rotation
    ball_model.rotation_x += ball.angular_velocity.x * time.dt
    ball_model.rotation_y += ball.angular_velocity.y * time.dt
    ball_model.rotation_z += ball.angular_velocity.z * time.dt

    for c in crowd_entities:
        c.y = 0.5 + 0.05 * math.sin(time.time() * 2 + c.idle_offset)

    

reset_for_serve()

app.run()
