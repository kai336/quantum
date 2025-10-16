import random
import time

lifetime = 12
number = 10
alpha = 0

class Link:
  def __init__(self, node1, node2, success_prob=0.1, lifetime=12):
    self.node1 = node1
    self.node2 = node2
    self.success_prob = success_prob
    self.entangled = False
    self.lifetime = 0
    self.succeed = False

  def attempt_entanglement(self):
    
    success = (random.random() < self.success_prob)
    if success:
      self.entangled = True
      self.lifetime = lifetime
      #print(f"Link between node {self.node1} and node {self.node2} succeeded.")
    else:
      #print(f"Link between node {self.node1} and node {self.node2} failed.")
      self.lifetime = 0
      
          
#建立TOPOLOGY
class Network:
    def __init__(self, num_nodes=7, num_links=6):
        self.nodes = list(range(1, num_nodes+1))
        self.links = []
        self.request_num = number
        self.request = []
        
        #创建链路
        for i in range(num_links):
            node1, node2 = self.nodes[i], self.nodes[i+1]
            self.links.append(Link(node1, node2))
        
        for r in range(self.request_num):
            self.request.append(self.links[0]) 
                                   

    def entanglement_gen(self):
        for link in self.links:
            if link.lifetime <= 0:
                link.entangled = False
                link.attempt_entanglement()
    

            

    def swap_entangled_links(self):
         
        for j in range(self.request_num):
            for i in range(len(self.links)):
                
            #对于可使用链路寿命进行限制
               # if self.links[i].lifetime <= alpha:
               #     self.links[i].lifetime = 0
               #     self.links[i].entangled = False
                #判断首个和第二个链路  
                if  self.request[j].node2 == 2:   
                    link1 = self.links[0]
                    link2 = self.links[1]
                    if link1.entangled and  link2.entangled :
                        new_link = Link(link1.node1, link2.node2)
                        #该行判定是否引入swap后的lifetime
                        new_link.lifetime = min(link1.lifetime, link2.lifetime)
                        if new_link.lifetime > 0:
                            new_link.entangled = True
                        link1.entangled = False
                        link1.lifetime = 0
                        link2.entangled = False
                        self.request[j] = new_link
                        link2.lifetime = 0
                        if new_link.lifetime <= 0:
                            self.request[j].lifetime = 0
                            self.request[j].entangled = False
                            self.request[j].node1 = 1
                            self.request[j].node2 = 2
                    
                    
                            
                            
                    #print('request',j+1,'node',self.request[j].node1,self.request[j].node2)
                         
                #完成swap并且寻找是否有可以向前swap的链路
                else:
                    link1 = self.request[j]
                    link2 = self.links[i]
                    if link1.entangled and link2.entangled and link1.node2 == link2.node1:
                        
                            new_link = Link(link1.node1, link2.node2)
                            #该行判定是否引入swap后的lifetime
                            new_link.lifetime = min(link1.lifetime, link2.lifetime)
                            if new_link.lifetime > 0:
                                new_link.entangled = True
                            link1.entangled = False
                            link1.lifetime = 0
                            link2.entangled = False
                            link2.lifetime = 0                        
                            self.request[j] = new_link
                            if new_link.lifetime <= 0:
                                self.request[j].lifetime = 0
                                self.request[j].entangled = False
                                self.request[j].node1 = 1
                                self.request[j].node2 = 2
                                break
                """                
                if  self.links[i].lifetime <= alpha:
                    self.links[i].lifetime = 0
                    self.links[i].entangled = False  
                """          
                          
                          #print('request',j+1,'node',self.request[j].node1,self.request[j].node2)
                    
                    
                        
                
        
                    

def exp1():
    
    network = Network()
    time_slot = 100000
    request_num = number
    total_time = 0
    
    
            
    for t in range(time_slot):
        #print("at time", t+1)
        
            
        if t == 0:
            network.entanglement_gen()
              
              
        if t > 0:
            network.swap_entangled_links()
            for link in network.links:
                if link.lifetime <= alpha:
                    link.lifetime = 0
                    link.entangled = False
            network.entanglement_gen()
                
                
        for link in network.links:
            link.lifetime = link.lifetime - 1
            """
            if link.lifetime <= alpha:
                link.lifetime = 0
                link.entangled = False
        """
                
    
        for n in range(len(network.request)):
            
            if t > 0:
                network.request[n].lifetime  = network.request[n].lifetime - 1
            #print(f"Request {n+1} from {network.request[n].node1} to {network.request[n].node2} in time{t+1} .life time is{network.request[n].lifetime} ")
             
            if network.request[n].node1 == 1 and network.request[n].node2 == 7 and network.request[n].succeed == False:
                print(f"Request {n+1} succeeded in time{t+1} .life time is{network.request[n].lifetime} ")
                network.request[n].succeed = True
                if n == (len(network.request) - 1):
                    total_time = total_time + t+1
                    print(total_time)
                    
                    """
            if network.request[n].succeed == False:
                for link in network.links:
                    if abs(link.lifetime - network.request[n].lifetime) >= alpha:
                        link.lifetime = 0
                        link.entangled = False
            break
            """
                
            
            
    return total_time

   

                
          
    

#exp1()

cicle = 40
t_time = 0
for c in range(cicle):
    print("in ciccle",c)
    t_time = exp1() + t_time
    
average_time = t_time/cicle

                
print(average_time)