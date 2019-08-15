from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import generics, filters, status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from reddit import tasks
from reddit.models import Post
from .serializers import (
    PostSerializer,
    PostUpdateRequest,
    RejectRequest,
    RejectResponse,
    PendingSubredditsResponse,
)


class PostViewMixin:
    queryset = Post.objects.pending()


class PostsListView(PostViewMixin, generics.ListAPIView):
    serializer_class = PostSerializer
    filter_backends = (filters.OrderingFilter, filters.SearchFilter)
    ordering_fields = ('created', 'score')
    search_fields = ('title',)

    def get_queryset(self):
        qs = super().get_queryset()
        subs = self.request.query_params.getlist('subs[]')
        if subs:
            qs = qs.filter(subreddit_name__in=subs)
        return qs

    @swagger_auto_schema(
        operation_id="get pending reddit posts list",
        manual_parameters=[
            openapi.Parameter(
                name='subs[]',
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_ARRAY,
                items=openapi.Items(openapi.TYPE_STRING),
                description="example: `?subs[]=pics&subs[]=gifs`",
            )
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PostView(PostViewMixin, generics.GenericAPIView):
    serializer_class = PostUpdateRequest

    @swagger_auto_schema(
        operation_id="publish single reddit post",
        responses={status.HTTP_201_CREATED: 'empty'},
    )
    def post(self, request: Request, *args, **kwargs):
        post = self.get_object()
        if post.status == Post.ACCEPTED:
            return Response(status=status.HTTP_201_CREATED)

        s: PostUpdateRequest = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        title = s.validated_data.get('title')
        post.status = Post.ALMOST
        if title:
            post.title = title
        post.save()
        tasks.publish_post_task.delay(post.id, bool(title))
        return Response(status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    operation_id="reject reddit posts in bulk",
    method='post',
    request_body=RejectRequest,
    responses={status.HTTP_200_OK: RejectResponse},
)
@api_view(['POST'])
def reject_view(request: Request):
    s = RejectRequest(data=request.data)
    s.is_valid(raise_exception=True)
    posts = Post.objects.filter(pk__in=s.validated_data['posts'])
    rows = posts.update(status=Post.REJECTED)
    res = RejectResponse(data={'rejected': rows})
    res.is_valid(raise_exception=True)
    return Response(res.validated_data)


@swagger_auto_schema(
    operation_id="get list of subreddits for currently pending posts",
    method='get',
    responses={status.HTTP_200_OK: PendingSubredditsResponse},
)
@api_view(['GET'])
def pending_subreddits_view(request: Request):
    s = PendingSubredditsResponse(data={
        'subreddits': list(Post.objects.pending_subs()),
    })
    s.is_valid(raise_exception=True)
    return Response(s.validated_data)
