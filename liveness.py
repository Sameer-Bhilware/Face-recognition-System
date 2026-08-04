import numpy as np

class LivenessDetector:
    def __init__(self):
        self.prev_center = None
        self.movement_detected = False

    def update(self, box):
        x1, y1, x2, y2 = box
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        current_center = np.array([center_x, center_y])

        if self.prev_center is not None:
            movement = np.linalg.norm(current_center - self.prev_center)

            if movement > 10:  # movement threshold
                self.movement_detected = True

        self.prev_center = current_center

    def is_live(self):
        return self.movement_detected

    def reset(self):
        self.movement_detected = False