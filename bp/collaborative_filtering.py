import numpy as np
from itertools import islice

from .util import db

class CollaborativeFiltering:
    def __init__(self):
        users = list(db.users.find({}))
        videos = list(db.videos.find({}))
        self.video_ids = [str(video['_id']) for video in videos]  # ObjectId
        self.u2i = {str(doc['_id']): idx for idx, doc in enumerate(users)}  # String ID
        self.v2i = {str(doc['_id']): idx for idx, doc in enumerate(videos)}  # String ID

        self.num_users = len(users)
        self.num_videos = len(videos)

        self.M = np.zeros((self.num_users, self.num_videos), dtype=np.int8)

        for video in videos:
            for like in video['likes']:
                self.M[self.u2i[str(like['user'])], self.v2i[str(video['_id'])]] = like['value']

    def add_user(self, user_id):
        self.u2i[user_id] = self.num_users
        self.num_users += 1
        self.M = np.vstack((self.M, np.zeros(self.M.shape[1], np.int8)))

    def add_video(self, video_id):
        self.video_ids.append(video_id)
        self.v2i[str(video_id)] = self.num_videos
        self.num_videos += 1
        self.M = np.hstack((self.M, np.zeros((self.M.shape[0],1), np.int8)))

    def add_like(self, user_id, video_id, value):
        self.M[self.u2i[user_id], self.v2i[video_id]] = value

    def user_based_recommendations(self, user_id, watched, count):
        print(f"Received request for {count} videos based on user {user_id}")
        user_idx = self.u2i[user_id]
        similarities = np.dot(self.M, self.M[user_idx])  # might need to change to cosine similarity
        predictions = np.dot(similarities, self.M)  # how our user would rate each video
        recommendations = np.argsort(predictions)[::-1]  # sort indices from highest to lowest rating
        watched = [self.v2i[vid] for vid in watched]
        watched_mask = np.isin(recommendations, watched)
        recommendations = np.concatenate((recommendations[~watched_mask], recommendations[watched_mask]))  # prioritize unwatched videos
        print(f"Top {count}:  {recommendations[:count]}")
        processing_videos = {vid['_id'] for vid in db.videos.find({'status': 'processing'})}
        print(f"Remove processing videos: {processing_videos}")
        print(f"Final list: {list(islice((vid_id for vid_idx in recommendations if (vid_id := self.video_ids[vid_idx]) not in processing_videos), count))}")
        return list(islice((vid_id for vid_idx in recommendations if (vid_id := self.video_ids[vid_idx]) not in processing_videos), count))

    def video_based_recommendations(self, video_id, watched, count):
        print(f"Received request for {count} videos based on user {video_id}")
        video_idx = self.v2i[video_id]
        similarities = np.dot(self.M[:, video_idx], self.M)  # how similar is each video to our video
        recommendations = np.argsort(similarities)[::-1]  # sort indices from highest to lowest rating
        watched = [self.v2i[vid] for vid in watched]
        watched_mask = np.isin(recommendations, watched)
        recommendations = np.concatenate((recommendations[~watched_mask], recommendations[watched_mask]))  # prioritize unwatched videos
        print(f"Top {count}:  {recommendations[:count]}")
        processing_videos = {vid['_id'] for vid in db.videos.find({'status': 'processing'})}
        return list(islice((vid_id for vid_idx in recommendations if (vid_id := self.video_ids[vid_idx]) not in processing_videos), count))

rec_algo = CollaborativeFiltering()