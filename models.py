import torch
from facenet_pytorch import InceptionResnetV1, MTCNN

# Reduce CPU thread overhead
torch.set_num_threads(2)
torch.backends.cudnn.benchmark = True

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# MTCNN for face detection & alignment (used in BOTH registration and recognition)
mtcnn = MTCNN(
    image_size=160,
    margin=20,
    keep_all=True,
    device=device,
    post_process=True  # normalizes to [-1, 1] automatically
)

# FaceNet embedding model
resnet = InceptionResnetV1(
    pretrained='vggface2'
).eval().to(device)
