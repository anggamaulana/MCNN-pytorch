import os
import torch
import torch.nn as nn
import visdom
import random
import argparse

from mcnn_model import MCNN
from my_dataloader import CrowdDataset


if __name__=="__main__":

    ap = argparse.ArgumentParser()
    ap.add_argument("-novis", "--novis", required=False, help="Deactivate visdom", action="store_true")
    ap.add_argument("-dataset", "--dataset", type=str, required=True, help="dataset root")
    ap.add_argument("-pretrained", "--pretrained", type=str, default="", help="path to pretrained model")
    ap.add_argument("-epoch", "--epoch", type=int, default=2000,
                    help="epoch")
    args = vars(ap.parse_args())

    torch.backends.cudnn.enabled=False
    vis = None
    if args["novis"]==False:
        vis=visdom.Visdom()

    device=torch.device("cuda")
    mcnn=MCNN().to(device)

    if args["pretrained"]!="":
        print("Load pretrained model", args["pretrained"])
        mcnn.load_state_dict(torch.load(args["pretrained"], map_location=device))

    criterion=nn.MSELoss(size_average=False).to(device)
    optimizer = torch.optim.SGD(mcnn.parameters(), lr=1e-6,
                                momentum=0.95)
    
    img_root = args["dataset"] + '/train_data/images'
    gt_dmap_root = args["dataset"] + '/train_data/ground_truth'
    dataset=CrowdDataset(img_root,gt_dmap_root,4)
    dataloader=torch.utils.data.DataLoader(dataset,batch_size=1,shuffle=True)

    test_img_root = args["dataset"] + '/test_data/images'
    test_gt_dmap_root = args["dataset"] + '/test_data/ground_truth'
    test_dataset=CrowdDataset(test_img_root,test_gt_dmap_root,4)
    test_dataloader=torch.utils.data.DataLoader(test_dataset,batch_size=1,shuffle=False)

    #training phase
    if not os.path.exists('./checkpoints'):
        os.mkdir('./checkpoints')
    min_mae=10000
    min_epoch=0
    train_loss_list=[]
    epoch_list=[]
    test_error_list=[]
    for epoch in range(0, args["epoch"]):

        mcnn.train()
        epoch_loss=0
        for i,(img,gt_dmap) in enumerate(dataloader):
            img=img.to(device)
            gt_dmap=gt_dmap.to(device)
            # forward propagation
            et_dmap=mcnn(img)
            # calculate loss
            loss=criterion(et_dmap,gt_dmap)
            epoch_loss+=loss.item()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        #print("epoch:",epoch,"loss:",epoch_loss/len(dataloader))
        epoch_list.append(epoch)
        train_loss_list.append(epoch_loss/len(dataloader))
        # torch.save(mcnn.state_dict(),'./checkpoints/epoch_'+str(epoch)+".param")

        mcnn.eval()
        mae=0
        for i,(img,gt_dmap) in enumerate(test_dataloader):
            img=img.to(device)
            gt_dmap=gt_dmap.to(device)
            # forward propagation
            et_dmap=mcnn(img)
            mae+=abs(et_dmap.data.sum()-gt_dmap.data.sum()).item()
            del img,gt_dmap,et_dmap
        if mae/len(test_dataloader)<min_mae:
            min_mae=mae/len(test_dataloader)
            min_epoch=epoch
            torch.save(mcnn.state_dict(),'./checkpoints/best.pth')
        test_error_list.append(mae/len(test_dataloader))
        print("epoch:"+str(epoch)+" error:"+str(mae/len(test_dataloader))+" min_mae:"+str(min_mae)+" min_epoch:"+str(min_epoch))
        if vis is not None:
            vis.line(win=1,X=epoch_list, Y=train_loss_list, opts=dict(title='train_loss'))
            vis.line(win=2,X=epoch_list, Y=test_error_list, opts=dict(title='test_error'))
        # show an image
        index=random.randint(0,len(test_dataloader)-1)
        img,gt_dmap=test_dataset[index]
        if vis is not None:
            vis.image(win=3,img=img,opts=dict(title='img'))
            vis.image(win=4,img=gt_dmap/(gt_dmap.max())*255,opts=dict(title='gt_dmap('+str(gt_dmap.sum())+')'))
        img=img.unsqueeze(0).to(device)
        gt_dmap=gt_dmap.unsqueeze(0)
        et_dmap=mcnn(img)
        et_dmap=et_dmap.squeeze(0).detach().cpu().numpy()
        if vis is not None:
            vis.image(win=5,img=et_dmap/(et_dmap.max())*255,opts=dict(title='et_dmap('+str(et_dmap.sum())+')'))
        


    import time
    print(time.strftime('%Y.%m.%d %H:%M:%S',time.localtime(time.time())))

        