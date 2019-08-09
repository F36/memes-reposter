import logging
import re
from html import unescape

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core import validators
from django.core.exceptions import ValidationError
from django.db import models

from .api import get_about, get_posts, get_reddit_url
from .utils import get_photo_url, get_video_url
from core.fields import URLField
from core.post import Post as NormalPost

TRASH_REGEX = re.compile(r'[^\w\s]')
logger = logging.getLogger(__name__)


class Subreddit(models.Model):
    name = models.CharField(
        max_length=255,
        help_text="Subreddit name or search criterion (eg 'popular' or 'all')",
    )
    active = models.BooleanField(default=True)
    score_limit = models.IntegerField(
        validators=[validators.MinValueValidator(0)],
        default=1000,
        help_text="Required score to be send to moderation.",
    )
    score_limit_repost = models.IntegerField(
        validators=[validators.MinValueValidator(0)],
        default=100000,
        help_text="Required score for automatic repost by bot.",
    )
    pass_nsfw = models.BooleanField(default=False)
    show_title = models.BooleanField(default=True)
    forbidden_keywords = ArrayField(models.CharField(max_length=255), default=list)

    def __str__(self):
        return f'Subreddit({self.name})'

    @property
    def url(self):
        return get_reddit_url(self.name, api=False)

    @property
    def forbidden_keywords_set(self):
        return set(self.forbidden_keywords)

    def clean(self):
        if self.score_limit > self.score_limit_repost:
            raise ValidationError("Invalid score limits. Score limit for repost should be higher.")

    def get_about(self):
        return get_about(self.name)

    def get_posts(self, limit: int = None):
        limit = limit or settings.REDDIT_POSTS_LIMIT
        return get_posts(self.name, limit)


class Post(models.Model):
    STATUS_ACCEPTED = 'accepted'
    STATUS_PENDING = 'pending'
    STATUS_ALMOST = 'almost'
    STATUS_REJECTED = 'rejected'
    STATUSES = (
        (STATUS_ACCEPTED, STATUS_ACCEPTED),
        (STATUS_PENDING, STATUS_PENDING),
        (STATUS_ALMOST, STATUS_ALMOST),
        (STATUS_REJECTED, STATUS_REJECTED),
    )

    status = models.CharField(max_length=200, choices=STATUSES, default=STATUS_ACCEPTED)
    created = models.DateTimeField(auto_now_add=True)

    reddit_id = models.CharField(max_length=200, unique=True)
    subreddit = models.ForeignKey(Subreddit, on_delete=models.CASCADE)
    subreddit_name = models.CharField(max_length=255)

    title = models.TextField()
    score = models.IntegerField()
    nsfw = models.BooleanField(default=False)
    comments = URLField(blank=True, null=True)

    url = URLField(null=True, blank=True)
    photo_url = URLField(null=True, blank=True)
    video_url = URLField(null=True, blank=True)
    text = models.TextField(null=True, blank=True)
    file_path = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'Post({self.reddit_id}, {self.title!r})'

    @property
    def title_terms(self):
        title = self.title.lower()
        title = TRASH_REGEX.sub('', title)
        return title.split()

    @property
    def comments_short(self):
        return f'https://redd.it/{self.reddit_id}'

    @classmethod
    def from_dict(cls, data: dict, subreddit: Subreddit):
        return Post(
            reddit_id=data['id'],
            subreddit=subreddit,
            subreddit_name=data['subreddit'],
            # meta
            title=unescape(data['title']),
            score=int(data['score']),
            nsfw=data['over_18'],
            comments='https://reddit.com' + data['permalink'],
            # content
            url=data['url'],
            photo_url=get_photo_url(data),
            video_url=get_video_url(data),
            text=data['selftext']
        )

    def normalize(self):
        return NormalPost(
            title=self.title,
            url=self.url,
            photo_url=self.photo_url,
            video_url=self.video_url,
            text=self.text,
            comments=self.comments,
            file_path=self.file_path,
        )