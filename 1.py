

import torch
import torch.nn as nn
from torch.nn import functional as F
import torchvision.datasets as dset
import torchvision.transforms as transforms
from torch.utils.data import DataLoader

transform = transforms.Compose([
     transforms.ToTensor(),
     transforms.Normalize(mean=(0.5),std=(0.5))]) 

train_dataset=dset.MNIST(root="..//yuanwei//data", train=True, transform=transform, target_transform=None, download=True)
val_dataset=dset.MNIST(root="..//yuanwei//data", train=False, transform=transform, target_transform=None, download=True)


train_loader = DataLoader(dataset=train_dataset,
                               batch_size=100,
                               shuffle=True)

test_loader = DataLoader(dataset=val_dataset,
                              batch_size=100)

class Identity_residual(nn.Module):  #权重全为0的RESNET块,输入通道必须等于输出通道
    def __init__(self, input_channels,kernel_size=3,strides=1):
        super().__init__()
        self.conv1 = nn.Conv2d(input_channels, input_channels, kernel_size=kernel_size,
                               padding=1, stride=strides)
        nn.init.normal_(self.conv1.weight,0,5)
        nn.init.normal_(self.conv1.weight,0,5)
        self.conv2 = nn.Conv2d(input_channels, input_channels, kernel_size=kernel_size,
                               padding=1)
        nn.init.normal_(self.conv1.weight,0,5)
        nn.init.normal_(self.conv1.weight,0,5)
        self.bn1 = nn.BatchNorm2d(input_channels)
        self.bn2 = nn.BatchNorm2d(input_channels)

    def forward(self, X):
        Y = F.relu(self.bn1(self.conv1(X)))
        Y = self.bn2(self.conv2(Y))
        Y += X
        return F.relu(Y)

class Output_layer(nn.Module):
    def __init__(self,input_channels,num_channels,num_class,dropout):
        super().__init__()
        self.fc1=nn.Linear(input_channels*28*28,num_channels)
        self.fc2=nn.Linear(num_channels,num_channels)
        self.fc3=nn.Linear(num_channels,num_class)
        self.dropout1 = nn.Dropout(dropout)
        self.dropout2 = nn.Dropout(dropout)
        self.flat=nn.Flatten()


    def forward(self,x):
        x = self.flat(x)
        x=self.fc1(x)
        x=self.dropout1(x)
        x=F.relu(x)
        x=self.fc2(x)
        x=self.dropout2(x)
        x=F.relu(x)
        x=self.fc3(x)
        return x

def basic_model(input_channels):
    output_layer=Output_layer(input_channels=input_channels,num_channels=256,num_class=10,dropout=0.5)
    net=nn.Sequential(nn.Conv2d(1,input_channels,kernel_size=3,padding=1,stride=1),Identity_residual(input_channels))
    net.add_module(f'output_layer',output_layer)
    return net

def copy_parameter(model,num_blocks,input_channels,n):
    #输入一个模型和其插入块的位置n，返回处理过参数的模型，供build调用


    net=nn.Sequential(nn.Conv2d(1,input_channels,kernel_size=3,padding=1,stride=1))
    net.weight=model[0].weight
    net.bias=model[0].bias
    output_layer=Output_layer(input_channels=input_channels,num_channels=256,num_class=10,dropout=0.5)
    for i in range(num_blocks):
        block=Identity_residual(input_channels=input_channels)
        if i<n:
            block.load_state_dict(model[i+1].state_dict())
            net.add_module(f'block{i}',block)
        if i==n:
            net.add_module(f'block{i}',block)
        if i>n:
            block.load_state_dict(model[i].state_dict())
            net.add_module(f'block{i}',block)
    net.add_module(f'output_layer',output_layer)
    return net

def build(model,num_blocks,input_channels):
    #输入一个模型，输出一个含有num_blocks个模型且每个模型含有num_blocks个块的列表，初始化模型需要单独写

    net=[]
    for i in range(num_blocks):
        net.append(copy_parameter(model,num_blocks,input_channels,i))
    return net

learning_rate=0.01
# Device configuration
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
# Hyper parameters
num_epochs = 5
num_classes = 10
batch_size = 100
num_block=5  #块的个数

def choice_model(model):                   #输入一个模型列表，输出这个列表中准确率最高的模型
    acc=[]
    for i in range(len(model)):
        model[i]=model[i].to(device)
        with torch.no_grad():
            correct=0.0
            total=0
            for images,labels in test_loader:
                images=images.to(device)
                labels=labels.to(device)
                outputs = model[i](images)
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
            acc.append(correct)
            
    m,index=torch.max(torch.tensor(acc),0)
    print('Accuracy of the model on the 10000 test images: {} %'.format( 100*m / total))
    print('the best position to insert is %d'%index)

    return model[index]

# Commented out IPython magic to ensure Python compatibility.
#输入一个模型进行训练,返回训练后的模型，和在验证集合上的准确率
def train_model(model):
    criterion=nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    model =model.to(device)

    total_step = len(train_loader)
    test_step=len(test_loader)
    for epoch in range(num_epochs):
        train_correct = 0.0
        loss_num=0
        total_loss=0.0
        for i, (images, labels) in enumerate(train_loader):
            images = images.to(device)
            labels = labels.to(device)
            outputs = model(images)
            _, pred = torch.max(outputs.data, 1)
            loss = criterion(outputs, labels)
            loss = loss.requires_grad_()

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            train_correct += torch.sum(pred == labels.data)
            loss_num+=1
            total_loss+=loss.item()

            #if (i+1) % 100 == 0:
            #    print ('Epoch [{}/{}], Step [{}/{}], Loss: {:.4f}'
            #            .format(epoch+1, num_epochs, i+1, total_step, loss.item()))

        
        test_correct = 0.0
        for data in test_loader:
            test_x,test_y=data
            test_x=test_x.to(device)
            test_y=test_y.to(device)
            outputs=model(test_x)
            _,pred=torch.max(outputs.data,1)
            test_correct += torch.sum(pred == test_y.data)

        print('Epoch [%d/%d] ,train acc %.3f, test acc %.3f, loss %.4f'
#                 %(epoch+1, num_epochs,float(train_correct) / total_step, test_correct/test_step, total_loss/loss_num))
        
    return model

def start_train(num_block,input_channels):
    #输入num_block,input_channels
    print('start train ...')

    for i in range(num_block):
        #i步有i+1个块完成训练输出一个训练后准确率最高的模型
        print()
        print('the model have %d residual block'%(i+1))
        net=[]
        if i==0:
            print('let us train the %dst model '%(i+1))
            model=train_model(basic_model(input_channels))
            net=[model]
            
        if i>0 and i<num_block-1:
            model=build(model=model,num_blocks=i+1,input_channels=input_channels)
            for j in range(i+1):
                print('let us train the %dst model '%(j+1))
                net.append(train_model(model[j]))  

        if i==num_block-1 and i!=0:
            model=build(model=model,num_blocks=i+1,input_channels=input_channels)
            for j in range(i+1):
                print('let us train the %dst model '%(j+1))
                net.append(train_model(model[j]))

        model=choice_model(net)
    return model

model=start_train(num_block=18,input_channels=16)
