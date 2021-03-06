# -*- coding: utf-8 -*-
"""
Created on Wed Aug 16 14:02:46 2017

@author: tunoat
"""

import torch
import torch.autograd as autograd
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

def prepare_sentence_sequence(seq, to_ix):
    idxs = [to_ix[w] for w in seq]
    tensor = torch.LongTensor(idxs)
    return autograd.Variable(tensor)
def prepare_word_sequence(seq, to_ix):
    idxs =[]
    for word in seq:
        idxs.append([to_ix[ch] for ch in word])
    tensor = []
    for i in idxs:
        tensor.append(autograd.Variable(torch.LongTensor(i)))
        
    return tensor

training_data = [
    ("The dog happily ate the apple".split(), ["DET", "NN", "ADV", "V", "DET", "NN"]),
    ("Everybody read that book silently".split(), ["NN", "V", "DET", "NN", "ADV"])
]
word_to_ix = {}
char_to_ix = {'PAD':0}
training_data2 = []
for sent, tags in training_data:
    for word in sent:
        training_data2.append((list(word),word))
        for char in word:
            if char not in char_to_ix:
                char_to_ix[char] = len(char_to_ix)
        if word not in word_to_ix:
            word_to_ix[word] = len(word_to_ix)

print(word_to_ix)
print(char_to_ix)
tag_to_ix = {"DET": 0, "NN": 1, "V": 2, "ADV": 3}

# These will usually be more like 32 or 64 dimensional.
# We will keep them small, so we can see how the weights change as we train.
WORD_EMBEDDING_DIM = 6
CHAR_EMBEDDING_DIM = 9
WORD_HIDDEN_DIM = 6
CHAR_REP_DIM = 3

######################################################################
# Create the model:


class LSTMTagger(nn.Module):

    def __init__(self, word_embedding_dim, char_embedding_dim, word_hidden_dim, word_vocab_size, char_vocab_size, char_rep_dim, tagset_size):
        super(LSTMTagger, self).__init__()
        self.char_rep_dim = char_rep_dim
        self.word_hidden_dim = word_hidden_dim

        self.char_embeddings = nn.Embedding(char_vocab_size, char_embedding_dim)
        self.word_embeddings = nn.Embedding(word_vocab_size, word_embedding_dim)

        # The LSTM takes word embeddings as inputs, and outputs hidden states
        # with dimensionality hidden_dim.
        self.lstm_word = nn.LSTM(char_embedding_dim, char_rep_dim)
        self.lstm_sentence = nn.LSTM(word_embedding_dim + char_rep_dim, word_hidden_dim)

        self.word_hidden2tag = nn.Linear(word_hidden_dim, tagset_size)
        self.word_hidden = self.word_init_hidden()
        self.sentence_hidden = self.sentence_init_hidden()

    def word_init_hidden(self):
        return (autograd.Variable(torch.zeros(1, 1, self.char_rep_dim)),
                autograd.Variable(torch.zeros(1, 1, self.char_rep_dim)))

    def sentence_init_hidden(self):
        return (autograd.Variable(torch.zeros(1, 1, self.word_hidden_dim)),
                autograd.Variable(torch.zeros(1, 1, self.word_hidden_dim)))
    
    def forward(self, word_list, sentence):
        representative_word_output = []
        for word in word_list:
            char_embeds = self.char_embeddings(word)
            word_lstm_out, self.word_hidden = self.lstm_word(
                char_embeds.view(len(word), 1, -1), self.word_hidden)
            representative_word_output.append(word_lstm_out[-1])
        rep_word_for_aug = representative_word_output[0]
        for i in representative_word_output[1:]:
            rep_word_for_aug = torch.cat((rep_word_for_aug, i), 0)
        word_embeds = self.word_embeddings(sentence)
        #print(torch.cat((word_embeds, rep_word_for_aug), 1))
        aug_word_embeds = torch.cat((word_embeds, rep_word_for_aug), 1)
        sentence_lstm_out, self.sentence_hidden = self.lstm_sentence(
            aug_word_embeds.view(len(sentence), 1, -1), self.sentence_hidden)
        tag_space = self.word_hidden2tag(sentence_lstm_out.view(len(sentence), -1))
        tag_scores = F.log_softmax(tag_space)
        return tag_scores
        
######################################################################
# Train the model:
model = LSTMTagger(WORD_EMBEDDING_DIM, CHAR_EMBEDDING_DIM, WORD_HIDDEN_DIM, len(word_to_ix), len(char_to_ix), CHAR_REP_DIM, len(tag_to_ix))
optimizer = optim.SGD(model.parameters(), lr=0.1)
loss_function = nn.NLLLoss()


for epoch in range(300):  # again, normally you would NOT do 300 epochs, it is toy data
    for sentence, tags in training_data:
        # Step 1. Remember that Pytorch accumulates gradients.
        # We need to clear them out before each instance
        model.zero_grad()

        # Also, we need to clear out the hidden state of the LSTM,
        # detaching it from its history on the last instance.

        model.word_hidden = model.word_init_hidden()
        model.sentence_hidden = model.sentence_init_hidden()
        # Step 2. Get our inputs ready for the network, that is, turn them into
        # Variables of word indices.
        sentence_in = prepare_sentence_sequence(sentence, word_to_ix)
        word_list_in = prepare_word_sequence(sentence, char_to_ix)
        targets = prepare_sentence_sequence(tags, tag_to_ix)

        # Step 3. Run our forward pass.
        tag_scores = model(word_list_in, sentence_in)

        # Step 4. Compute the loss, gradients, and update the parameters by
        #  calling optimizer.step()
        loss = loss_function(tag_scores, targets)
        loss.backward(retain_graph=True)
        optimizer.step()
    print(epoch)

# See what the scores are after training
inputs = prepare_sentence_sequence(training_data[0][0], word_to_ix)
word_list_in = prepare_word_sequence(training_data[0][0], char_to_ix)
tag_scores = model(word_list_in, inputs)
# The sentence is "the dog ate the apple".  i,j corresponds to score for tag j
#  for word i. The predicted tag is the maximum scoring tag.
# Here, we can see the predicted sequence below is 0 1 2 0 1
# since 0 is index of the maximum value of row 1,
# 1 is the index of maximum value of row 2, etc.
# Which is DET NOUN VERB DET NOUN, the correct sequence!
print(tag_scores)
