import torch
import time

device = torch.device("cuda")

x = torch.randn(5000, 5000).to(device)

start = time.time()
for _ in range(50):
    y = torch.mm(x, x)
torch.cuda.synchronize()
print("Time:", time.time() - start)