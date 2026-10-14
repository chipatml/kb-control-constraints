"""Card strings the sample constraints must produce."""

C1_CARD = (
    "CONSTRAINT c1: j1.joint_velocity <= 3.141593 RAD-PER-SEC "
    "(original: 180.0 DEG-PER-SEC; hardness: hard). "
    'SOURCE: UR5e_spec.pdf p.4: "Max joint speed: ±180°/s"'
)

C2_CARD = (
    "CONSTRAINT c2: arm1.tcp_speed <= 0.250000 M-PER-SEC "
    "(original: 0.25 M-PER-SEC; hardness: hard). "
    'SOURCE: Safety_manual.pdf p.12: "Reduce TCP speed to 250 mm/s when operators are present."'
)
