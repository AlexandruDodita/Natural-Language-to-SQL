CREATE TABLE badges
(
    Id     INTEGER          not null
        primary key,
    UserId INTEGER          null,
    Name   TEXT null,
    Date   DATETIME     null,
        foreign key (UserId) references users (Id)
            on update cascade on delete cascade
);

-- badges column meanings:
--   Id : the badge id
--   UserId : User Id; the unique id of the user
--   Name : the badge name the user obtained
--   Date : the date that the user obtained the badge

CREATE TABLE comments
(
    Id              INTEGER          not null
        primary key,
    PostId          INTEGER          null,
    Score           INTEGER          null,
    Text            TEXT     null,
    CreationDate    DATETIME     null,
    UserId          INTEGER          null,
    UserDisplayName TEXT null,
        foreign key (PostId) references posts (Id)
            on update cascade on delete cascade,
        foreign key (UserId) references users (Id)
            on update cascade on delete cascade
);

-- comments column meanings:
--   Id : the comment Id
--   PostId : Post Id; the unique id of the post
--   Score : rating score; commonsense evidence: The score is from 0 to 100. The score more than 60 refers that the comment is a positive comment. The score less than 60 refers that the comment is a negative comment.
--   Text : the detailed content of the comment
--   CreationDate : Creation Date; the creation date of the comment
--   UserId : User Id; the id of the user who post the comment
--   UserDisplayName : User Display Name; user's display name

CREATE TABLE postHistory
(
    Id                INTEGER          not null UNIQUE
        primary key,
    PostHistoryTypeId INTEGER          null,
    PostId            INTEGER          null,
    RevisionGUID      TEXT null,
    CreationDate      DATETIME     null,
    UserId            INTEGER          null,
    Text              TEXT     null,
    Comment           TEXT         null,
    UserDisplayName   TEXT null,
        foreign key (PostId) references posts (Id)
            on update cascade on delete cascade,
        foreign key (UserId) references users (Id)
            on update cascade on delete cascade
);

-- postHistory column meanings:
--   Id : the post history id
--   PostHistoryTypeId : Post History Type Id; the id of the post history type
--   PostId : Post Id; the unique id of the post
--   RevisionGUID : Revision GUID; the revision globally unique id of the post
--   CreationDate : Creation Date; the creation date of the post
--   UserId : User Id; the user who post the post
--   Text : the detailed content of the post
--   Comment : comments of the post
--   UserDisplayName : User Display Name; user's display name

CREATE TABLE postLinks
(
    Id            INTEGER      not null
        primary key,
    CreationDate  DATETIME null,
    PostId        INTEGER      null,
    RelatedPostId INTEGER      null,
    LinkTypeId    INTEGER      null,
        foreign key (PostId) references posts (Id)
            on update cascade on delete cascade,
        foreign key (RelatedPostId) references posts (Id)
            on update cascade on delete cascade
);

-- postLinks column meanings:
--   Id : the post link id
--   CreationDate : Creation Date; the creation date of the post link
--   PostId : Post Id; the post id
--   RelatedPostId : Related Post Id; the id of the related post
--   LinkTypeId : Link Type Id; the id of the link type

CREATE TABLE posts
(
    Id                    INTEGER          not null UNIQUE
        primary key,
    PostTypeId            INTEGER          null,
    AcceptedAnswerId      INTEGER          null,
    CreaionDate           DATETIME     null,
    Score                 INTEGER          null,
    ViewCount             INTEGER          null,
    Body                  TEXT     null,
    OwnerUserId           INTEGER          null,
    LasActivityDate       DATETIME     null,
    Title                 TEXT null,
    Tags                  TEXT null,
    AnswerCount           INTEGER          null,
    CommentCount          INTEGER          null,
    FavoriteCount         INTEGER          null,
    LastEditorUserId      INTEGER          null,
    LastEditDate          DATETIME     null,
    CommunityOwnedDate    DATETIME    null,
    ParentId              INTEGER          null,
    ClosedDate            DATETIME     null,
    OwnerDisplayName      TEXT null,
    LastEditorDisplayName TEXT null,
        foreign key (LastEditorUserId) references users (Id)
            on update cascade on delete cascade,
        foreign key (OwnerUserId) references users (Id)
            on update cascade on delete cascade,
        foreign key (ParentId) references posts (Id)
            on update cascade on delete cascade
);

-- posts column meanings:
--   Id : the post id
--   PostTypeId : Post Type Id; the id of the post type
--   AcceptedAnswerId : Accepted Answer Id; the accepted answer id of the post
--   CreaionDate : Creation Date; the creation date of the post
--   Score : the score of the post
--   ViewCount : View Count; the view count of the post; commonsense evidence: Higher view count means the post has higher popularity
--   Body : the body of the post
--   OwnerUserId : Owner User Id; the id of the owner user
--   LasActivityDate : Last Activity Date; the last activity date
--   Title : the title of the post
--   Tags : the tag of the post
--   AnswerCount : Answer Count; the total number of answers of the post
--   CommentCount : Comment Count; the total number of comments of the post
--   FavoriteCount : Favorite Count; the total number of favorites of the post; commonsense evidence: more favorite count refers to more valuable posts.
--   LastEditorUserId : Last Editor User Id; the id of the last editor
--   LastEditDate : Last Edit Date; the last edit date
--   CommunityOwnedDate : Community Owned Date; the community owned date
--   ParentId : the id of the parent post; commonsense evidence: If the parent id is null, the post is the root post. Otherwise, the post is the child post of other post.
--   ClosedDate : Closed Date; the closed date of the post; commonsense evidence: if ClosedDate is null or empty, it means this post is not well-finished if CloseDate is not null or empty, it means this post has well-finished.
--   OwnerDisplayName : Owner Display Name; the display name of the post owner
--   LastEditorDisplayName : Last Editor Display Name; the display name of the last editor

CREATE TABLE tags
(
    Id            INTEGER          not null
        primary key,
    TagName       TEXT null,
    Count         INTEGER          null,
    ExcerptPostId INTEGER          null,
    WikiPostId    INTEGER          null,
    foreign key (ExcerptPostId) references posts (Id)
        on update cascade on delete cascade
);

-- tags column meanings:
--   Id : the tag id
--   TagName : Tag Name; the name of the tag
--   Count : the count of posts that contain this tag; more counts --> this tag is more popular
--   ExcerptPostId : Excerpt Post Id; the excerpt post id of the tag
--   WikiPostId : Wiki Post Id; the wiki post id of the tag

CREATE TABLE users
(
    Id              INTEGER          not null UNIQUE
        primary key,
    Reputation      INTEGER          null,
    CreationDate    DATETIME     null,
    DisplayName     TEXT null,
    LastAccessDate  DATETIME     null,
    WebsiteUrl      TEXT null,
    Location        TEXT null,
    AboutMe         TEXT     null,
    Views           INTEGER          null,
    UpVotes         INTEGER          null,
    DownVotes       INTEGER          null,
    AccountId       INTEGER          null,
    Age             INTEGER          null,
    ProfileImageUrl TEXT null
);

-- users column meanings:
--   Id : the user id
--   Reputation : the user's reputation; commonsense evidence: The user with higher reputation has more influence.
--   CreationDate : Creation Date; the creation date of the user account
--   DisplayName : Display Name; the user's display name
--   LastAccessDate : Last Access Date; the last access date of the user account
--   WebsiteUrl : Website Url; the website url of the user account
--   Location : user's location
--   AboutMe : About Me; the self introduction of the user
--   Views : the number of views
--   UpVotes : the number of upvotes
--   DownVotes : the number of downvotes
--   AccountId : Account Id; the unique id of the account
--   Age : user's age;  teenager: 13-18  adult: 19-65  elder: > 65
--   ProfileImageUrl : Profile Image Url; the profile image url

CREATE TABLE votes
(
    Id           INTEGER  not null
        primary key,
    PostId       INTEGER  null,
    VoteTypeId   INTEGER  null,
    CreationDate DATE null,
    UserId       INTEGER  null,
    BountyAmount INTEGER  null,
        foreign key (PostId) references posts (Id)
            on update cascade on delete cascade,
        foreign key (UserId) references users (Id)
            on update cascade on delete cascade
);

-- votes column meanings:
--   Id : the vote id
--   PostId : Post Id; the id of the post that is voted
--   VoteTypeId : Vote Type Id; the id of the vote type
--   CreationDate : Creation Date; the creation date of the vote
--   UserId : User Id; the id of the voter
--   BountyAmount : Bounty Amount; the amount of bounty
